"""HW8 shared helpers for the Planner, Writer and Reviewer processes.

Agents never call each other: each one reads one topic and writes the next.
    inbox -> Planner -> tasks -> Writer -> drafts -> Reviewer -> final

Part 3 fixes are on by default; the --no-* / --auto-commit switches bring back the "before fix" behaviour:
    --no-idempotency   a replayed correlation_id is processed again
    --auto-commit      offsets are committed in the background, even before processing finishes
    --no-dlq           an exception stops the agent (no retries, no dead-letter topic)
    --mock SECONDS     no LLM call, fixed text after a delay (used by the failure tests)
    --instance N       name for a second copy of the same agent in one consumer group
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, ConsumerRebalanceListener

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PREFIX = "s6758"
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
INBOX, TASKS, DRAFTS, FINAL = (f"{PREFIX}_inbox", f"{PREFIX}_tasks", f"{PREFIX}_drafts", f"{PREFIX}_final")
DEAD_LETTER = f"{PREFIX}_dead_letter"
MODEL = "llama3.2:3b"
SEED = 6758
MAX_ATTEMPTS = 3
JOURNEY_LOG = Path(os.getenv("HW8_LOG", ROOT / "reports" / "hw08" / "raw" / "part2_journey.jsonl"))
STATE_DB = Path(os.getenv("HW8_STATE", Path(__file__).resolve().parent / ".state" / "processed.sqlite"))

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--no-idempotency", action="store_true")
parser.add_argument("--auto-commit", action="store_true")
parser.add_argument("--no-dlq", action="store_true")
parser.add_argument("--mock", type=float, default=None)
parser.add_argument("--instance", default="")
OPTS, _ = parser.parse_known_args()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def log(agent: str, event: str, **fields) -> None:
    extra = " ".join(f"{k}={json.dumps(v)}" for k, v in fields.items())
    print(f"{now()} [{agent}] {event} {extra}".rstrip(), flush=True)
    JOURNEY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with JOURNEY_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now(), "agent": agent, "event": event, **fields}) + "\n")


def llm(system: str, user: str, as_json: bool = False) -> str:
    from src.model_client import ModelClient

    kwargs = {"format": "json"} if as_json else {}
    client = ModelClient(model=MODEL, temperature=0.0, verbose=False, seed=SEED, num_predict=400, **kwargs)
    return client.complete([{"role": "system", "content": system}, {"role": "user", "content": user}])["text"].strip()


def encode(message: dict) -> bytes:
    return json.dumps(message).encode()


async def start(client, agent):
    for attempt in range(1, 31):
        try:
            await client.start()
            return client
        except Exception as exc:
            log(agent, f"Kafka not ready, retry {attempt}", error=str(exc))
            await asyncio.sleep(2)
    raise RuntimeError(f"cannot reach Kafka at {BOOTSTRAP}")


class ProcessedStore:
    """Idempotency: correlation_ids an agent has already finished, kept on disk so a restart remembers them."""

    def __init__(self, agent: str):
        STATE_DB.parent.mkdir(parents=True, exist_ok=True)
        self.agent = agent
        self.db = sqlite3.connect(STATE_DB, timeout=10)
        self.db.execute("CREATE TABLE IF NOT EXISTS processed (agent TEXT, correlation_id TEXT, at TEXT, "
                        "PRIMARY KEY (agent, correlation_id))")
        self.db.commit()

    def seen(self, cid: str) -> bool:
        return self.db.execute("SELECT 1 FROM processed WHERE agent = ? AND correlation_id = ?",
                               (self.agent, cid)).fetchone() is not None

    def add(self, cid: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO processed VALUES (?, ?, ?)", (self.agent, cid, now()))
        self.db.commit()


class LogAssignment(ConsumerRebalanceListener):
    def __init__(self, name):
        self.name = name

    async def on_partitions_revoked(self, revoked):
        pass

    async def on_partitions_assigned(self, assigned):
        log(self.name, "partitions assigned", partitions=sorted(tp.partition for tp in assigned))


async def run_agent(agent: str, in_topic: str, out_topic: str, handle) -> None:
    """Consume in_topic, call handle(message) -> outgoing message, send it to out_topic.

    Fixes (on unless switched off): skip correlation_ids already processed, retry a failing message up to
    MAX_ATTEMPTS times and then park it on the dead-letter topic, and commit the offset only after the
    outgoing message was delivered.
    """
    name = f"{agent}-{OPTS.instance}" if OPTS.instance else agent
    store = None if OPTS.no_idempotency else ProcessedStore(agent)
    consumer = AIOKafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=f"{PREFIX}-{agent.lower()}",
                                auto_offset_reset="earliest", enable_auto_commit=OPTS.auto_commit,
                                auto_commit_interval_ms=500)
    await start(consumer, name)
    consumer.subscribe([in_topic], listener=LogAssignment(name))
    producer = await start(AIOKafkaProducer(bootstrap_servers=BOOTSTRAP), name)
    log(name, f"listening on {in_topic}, sending to {out_topic}",
        idempotency=store is not None, commit="auto (background)" if OPTS.auto_commit else "after processing",
        dead_letter=not OPTS.no_dlq, mock=OPTS.mock is not None)
    try:
        async for msg in consumer:
            cid, extra = None, {}
            try:
                peek = json.loads(msg.value.decode())
                cid = peek.get("correlation_id")
                extra = {k: peek[k] for k in ("entity_id", "seq") if k in peek}
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                pass
            log(name, f"received from {msg.topic}", correlation_id=cid, partition=msg.partition, offset=msg.offset,
                **extra)

            if store and cid and store.seen(cid):
                log(name, "duplicate correlation_id, already processed - skipped", correlation_id=cid)
                await commit(consumer, name, msg)
                continue

            out, error = None, None
            for attempt in range(1, (1 if OPTS.no_dlq else MAX_ATTEMPTS) + 1):
                try:
                    message = json.loads(msg.value.decode())
                    out = await asyncio.to_thread(handle, message)
                    break
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    if OPTS.no_dlq:
                        log(name, "processing failed, agent stops (no retry, no dead-letter)", correlation_id=cid,
                            offset=msg.offset, error=error)
                        raise
                    log(name, f"attempt {attempt}/{MAX_ATTEMPTS} failed", correlation_id=cid, offset=msg.offset,
                        error=error)
                    await asyncio.sleep(0.5 * attempt)

            if out is None:
                bad = {"source_topic": msg.topic, "partition": msg.partition, "offset": msg.offset,
                       "correlation_id": cid, "error": error, "attempts": MAX_ATTEMPTS, "failed_at": now(),
                       "agent": name, "value": msg.value.decode(errors="replace")}
                meta = await producer.send_and_wait(DEAD_LETTER, encode(bad))
                log(name, f"moved to {DEAD_LETTER} after {MAX_ATTEMPTS} attempts", correlation_id=cid,
                    dead_letter_offset=meta.offset)
                await commit(consumer, name, msg)
                continue

            out["correlation_id"] = cid  # unchanged at every stage
            out["trace"] = message.get("trace", []) + [{"agent": name, "at": now()}]
            meta = await producer.send_and_wait(out_topic, encode(out), key=cid.encode() if cid else None)
            log(name, f"sent to {out_topic}", correlation_id=cid, partition=meta.partition, offset=meta.offset,
                **extra)
            if store and cid:
                store.add(cid)
            await commit(consumer, name, msg)
    finally:
        await consumer.stop()
        await producer.stop()


async def commit(consumer, name, msg):
    if OPTS.auto_commit:
        return  # the background auto-commit already moved the offset
    await consumer.commit()
    log(name, "offset committed", partition=msg.partition, committed_offset=msg.offset + 1)
