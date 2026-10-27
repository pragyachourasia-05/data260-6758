"""HW8 Part 2 shared helpers for the Planner, Writer and Reviewer processes.

Agents never call each other: each one reads one topic and writes the next.
    inbox -> Planner -> tasks -> Writer -> drafts -> Reviewer -> final
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PREFIX = "s6758"
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
INBOX, TASKS, DRAFTS, FINAL = (f"{PREFIX}_inbox", f"{PREFIX}_tasks", f"{PREFIX}_drafts", f"{PREFIX}_final")
MODEL = "llama3.2:3b"
SEED = 6758
JOURNEY_LOG = ROOT / "reports" / "hw08" / "raw" / "part2_journey.jsonl"


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


async def run_agent(agent: str, in_topic: str, out_topic: str, handle) -> None:
    """Consume in_topic, call handle(message) -> outgoing message, send it to out_topic.

    The offset is committed only after the outgoing message was delivered.
    """
    consumer = await start(AIOKafkaConsumer(in_topic, bootstrap_servers=BOOTSTRAP, group_id=f"{PREFIX}-{agent.lower()}",
                                            auto_offset_reset="earliest", enable_auto_commit=False), agent)
    producer = await start(AIOKafkaProducer(bootstrap_servers=BOOTSTRAP), agent)
    log(agent, f"listening on {in_topic}, sending to {out_topic}")
    try:
        async for msg in consumer:
            message = json.loads(msg.value.decode())
            cid = message.get("correlation_id")
            log(agent, f"received from {msg.topic}", correlation_id=cid, partition=msg.partition, offset=msg.offset)
            out = await asyncio.to_thread(handle, message)
            out["correlation_id"] = cid  # unchanged at every stage
            out["trace"] = message.get("trace", []) + [{"agent": agent, "at": now()}]
            meta = await producer.send_and_wait(out_topic, encode(out), key=cid.encode() if cid else None)
            log(agent, f"sent to {out_topic}", correlation_id=cid, partition=meta.partition, offset=meta.offset)
            await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()
