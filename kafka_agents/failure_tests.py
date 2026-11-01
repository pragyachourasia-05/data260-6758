"""HW8 Part 3 failure tests. Each test runs twice: before the fix and after the fix.

    python failure_tests.py duplicate
    python failure_tests.py consumer_death
    python failure_tests.py poison
    python failure_tests.py ordering
    python failure_tests.py all

Agents run as separate processes (same planner.py / writer.py / reviewer.py as Part 2) in --mock mode so
the tests do not wait on the LLM. Topics and consumer groups are recreated before every run.
Logs: reports/hw08/raw/part3/<test>_<before|after>_<agent>.log, results: reports/hw08/raw/part3_results.json
"""
import asyncio
import csv
import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer, TopicPartition
from common import BOOTSTRAP, DEAD_LETTER, DRAFTS, FINAL, INBOX, PREFIX, TASKS, encode

HERE = Path(__file__).resolve().parent
RAW = HERE.parent / "reports" / "hw08" / "raw"
OUT = RAW / "part3"
VERIFY_SEED = 266758
KAFKA_TOPICS = ["docker", "exec", "s6758_kafka", "/opt/kafka/bin/kafka-topics.sh", "--bootstrap-server", "localhost:9092"]
KAFKA_GROUPS = ["docker", "exec", "s6758_kafka", "/opt/kafka/bin/kafka-consumer-groups.sh",
                "--bootstrap-server", "localhost:9092"]


def say(text=""):
    print(text, flush=True)


# ---------- Kafka helpers ----------
def reset(topics: dict, groups: list):
    for g in groups:
        subprocess.run(KAFKA_GROUPS + ["--delete", "--group", g], capture_output=True)
    for t in topics:
        subprocess.run(KAFKA_TOPICS + ["--delete", "--if-exists", "--topic", t], capture_output=True)
    for t, parts in topics.items():
        for _ in range(30):
            r = subprocess.run(KAFKA_TOPICS + ["--create", "--if-not-exists", "--topic", t, "--partitions", str(parts),
                                               "--replication-factor", "1"], capture_output=True, text=True)
            if r.returncode == 0 and "marked for deletion" not in (r.stdout + r.stderr):
                break
            time.sleep(1)


async def _produce(topic, items):
    p = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP)
    await p.start()
    metas = []
    try:
        for value, key, partition in items:
            metas.append(await p.send_and_wait(topic, value if isinstance(value, bytes) else encode(value),
                                               key=key.encode() if key else None, partition=partition))
    finally:
        await p.stop()
    return [(m.partition, m.offset) for m in metas]


def produce(topic, items):
    """items: list of (value, key, partition)."""
    return asyncio.run(_produce(topic, items))


async def _read(topic):
    c = AIOKafkaConsumer(bootstrap_servers=BOOTSTRAP, enable_auto_commit=False)
    await c.start()
    try:
        parts = c.partitions_for_topic(topic) or {0}
        tps = [TopicPartition(topic, p) for p in parts]
        c.assign(tps)
        await c.seek_to_beginning(*tps)
        out = []
        while True:
            batch = await c.getmany(*tps, timeout_ms=1500)
            if not batch:
                return out
            out += [json.loads(m.value) for msgs in batch.values() for m in msgs]
    finally:
        await c.stop()


def read_topic(topic):
    return asyncio.run(_read(topic))


async def _committed(group, topic, partition):
    c = AIOKafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=group, enable_auto_commit=False)
    await c.start()
    try:
        return await c.committed(TopicPartition(topic, partition))
    finally:
        await c.stop()


def committed(agent, topic, partition):
    return asyncio.run(_committed(f"{PREFIX}-{agent}", topic, partition))


# ---------- agent processes ----------
class Agents:
    def __init__(self, test, mode):
        self.test, self.mode, self.procs = test, mode, {}
        OUT.mkdir(parents=True, exist_ok=True)
        self.state = OUT / f"{test}_{mode}.sqlite"
        self.state.unlink(missing_ok=True)

    def path(self, label, ext):
        return OUT / f"{self.test}_{self.mode}_{label}.{ext}"

    def start(self, script, label, *flags, fresh=True):
        if fresh:
            self.path(label, "log").unlink(missing_ok=True)
            self.path(label, "jsonl").unlink(missing_ok=True)
        env = {**os.environ, "HW8_LOG": str(self.path(label, "jsonl")), "HW8_STATE": str(self.state),
               "PYTHONIOENCODING": "utf-8"}
        logf = self.path(label, "log").open("a", encoding="utf-8")
        self.procs[label] = subprocess.Popen([sys.executable, "-u", script, *flags], cwd=HERE, env=env,
                                             stdout=logf, stderr=subprocess.STDOUT)
        say(f"  started {label}: python {script} {' '.join(flags)}  (pid {self.procs[label].pid})")

    def kill(self, label):
        subprocess.run(["taskkill", "/PID", str(self.procs[label].pid), "/T", "/F"], capture_output=True)
        self.procs[label].wait()

    def stop_all(self):
        for label in list(self.procs):
            if self.procs[label].poll() is None:
                self.kill(label)

    def events(self, label):
        p = self.path(label, "jsonl")
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []

    def wait(self, label, predicate, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            if any(predicate(e) for e in self.events(label)):
                return True
            if self.procs[label].poll() is not None:
                return False
            time.sleep(0.3)
        return False

    def wait_assigned(self, labels, timeout=60):
        for label in labels:
            self.wait(label, lambda e: e["event"] == "partitions assigned", timeout)

    def log_lines(self, label):
        p = self.path(label, "log")
        return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def show(lines, keep=None, limit=40):
    for ln in [x for x in lines if keep is None or any(k in x for k in keep)][:limit]:
        say("    " + (ln if len(ln) < 220 else ln[:220] + " ..."))


# ---------- 1. duplicate delivery ----------
def duplicate(mode):
    flags = ["--mock", "0.3"] + (["--no-idempotency"] if mode == "before" else [])
    reset({INBOX: 1, TASKS: 2, DRAFTS: 1, FINAL: 1}, [f"{PREFIX}-planner", f"{PREFIX}-writer", f"{PREFIX}-reviewer"])
    a = Agents("duplicate", mode)
    for agent in ("planner", "writer", "reviewer"):
        a.start(f"{agent}.py", agent, *flags)
    a.wait_assigned(["planner", "writer", "reviewer"])
    cid = f"dup-{mode}-{uuid.uuid4().hex[:8]}"
    message = {"correlation_id": cid, "question": "Is a 12-month lease better than month-to-month near SJSU?"}
    say(f"  send question correlation_id={cid}")
    produce(INBOX, [(message, cid, None)])
    a.wait("reviewer", lambda e: e["event"].startswith("sent to") and e.get("correlation_id") == cid, 60)
    say(f"  replay the same message (same correlation_id={cid})")
    produce(INBOX, [(message, cid, None)])
    time.sleep(6)
    a.stop_all()
    finals = [m for m in read_topic(FINAL) if m.get("correlation_id") == cid]
    runs = {ag: sum(1 for e in a.events(ag) if e["event"].startswith("sent to") and e.get("correlation_id") == cid)
            for ag in ("planner", "writer", "reviewer")}
    skipped = sum(1 for ag in ("planner", "writer", "reviewer") for e in a.events(ag) if "duplicate" in e["event"])
    say("  planner log:")
    show(a.log_lines("planner"), keep=[cid])
    result = {"correlation_id": cid, "messages_in_final": len(finals), "agent_runs": runs, "duplicates_skipped": skipped}
    say(f"  RESULT {mode}: {json.dumps(result)}")
    return result


# ---------- 2. consumer killed mid-work ----------
def consumer_death(mode):
    reset({TASKS: 2, DRAFTS: 1}, [f"{PREFIX}-writer"])
    a = Agents("consumer_death", mode)
    commit_flag = ["--auto-commit"] if mode == "before" else []
    a.start("writer.py", "writer", "--mock", "15", *commit_flag)
    a.wait_assigned(["writer"])
    cid = f"kill-{mode}-{uuid.uuid4().hex[:8]}"
    task = {"correlation_id": cid, "question": "Which documents does a landlord usually ask for?",
            "plan": ["List documents", "Explain each", "Keep it short"]}
    (partition, offset), = produce(TASKS, [(task, cid, None)])
    say(f"  sent task correlation_id={cid} to {TASKS} partition={partition} offset={offset}")
    a.wait("writer", lambda e: e["event"].startswith("received") and e.get("correlation_id") == cid, 30)
    time.sleep(3)  # Writer is in the middle of its 15 s of work
    a.kill("writer")
    at_kill = committed("writer", TASKS, partition)
    say(f"  killed Writer mid-processing; committed offset for partition {partition} = {at_kill}")
    a.start("writer.py", "writer", "--mock", "1", *commit_flag, fresh=False)
    say("  restarted Writer")
    done = a.wait("writer", lambda e: e["event"].startswith("sent to") and e.get("correlation_id") == cid, 25)
    time.sleep(2)
    a.stop_all()
    received = sum(1 for e in a.events("writer") if e["event"].startswith("received") and e.get("correlation_id") == cid)
    drafts = [m for m in read_topic(DRAFTS) if m.get("correlation_id") == cid]
    after = committed("writer", TASKS, partition)
    say("  writer log (both runs):")
    show(a.log_lines("writer"), keep=[cid, "offset committed", "listening", "assigned"])
    result = {"correlation_id": cid, "partition": partition, "message_offset": offset,
              "committed_offset_when_killed": at_kill, "times_received": received,
              "redelivered_after_restart": received >= 2, "draft_written": bool(done), "drafts_in_topic": len(drafts),
              "committed_offset_at_end": after}
    say(f"  RESULT {mode}: {json.dumps(result)}")
    return result


# ---------- 3. poison message ----------
def poison(mode):
    reset({TASKS: 2, DRAFTS: 1, DEAD_LETTER: 1}, [f"{PREFIX}-writer"])
    a = Agents("poison", mode)
    flags = ["--mock", "0.2"] + (["--no-dlq"] if mode == "before" else [])
    a.start("writer.py", "writer", *flags)
    a.wait_assigned(["writer"])
    bad = {"correlation_id": f"poison-{mode}", "question": "bad task", "plan": "this should be a list"}
    good = {"correlation_id": f"good-{mode}", "question": "Is renters insurance worth it?",
            "plan": ["Say what it covers", "Give the cost", "Recommend"]}
    sent = produce(TASKS, [(bad, None, 0), (good, None, 0)])  # same partition, poison first
    say(f"  sent poison then good message to {TASKS} partition 0 at offsets {[o for _, o in sent]}")
    crashes = 0
    if mode == "before":
        for _ in range(2):  # the agent dies; restart it once like a supervisor would
            end = time.time() + 20
            while a.procs["writer"].poll() is None and time.time() < end:
                time.sleep(0.3)
            if a.procs["writer"].poll() is None:
                break
            crashes += 1
            say(f"  Writer exited (crash {crashes}, exit code {a.procs['writer'].returncode})")
            if crashes == 1:
                a.start("writer.py", "writer", *flags, fresh=False)
                say("  restarted Writer")
    else:
        a.wait("writer", lambda e: e["event"].startswith("sent to") and e.get("correlation_id") == good["correlation_id"],
               30)
    time.sleep(2)
    a.stop_all()
    drafts = read_topic(DRAFTS)
    dead = read_topic(DEAD_LETTER)
    attempts = sum(1 for e in a.events("writer") if "failed" in e["event"])
    say("  writer log:")
    show(a.log_lines("writer"), keep=["poison", "good", "dead_letter", "Traceback", "ValueError", "listening"])
    result = {"crashes": crashes, "failed_attempts_logged": attempts, "dead_letter_messages": len(dead),
              "dead_letter_sample": {k: dead[0][k] for k in ("correlation_id", "error", "attempts", "source_topic",
                                                            "offset")} if dead else None,
              "good_message_processed": any(d.get("correlation_id") == good["correlation_id"] for d in drafts),
              "committed_offset_partition0": committed("writer", TASKS, 0)}
    say(f"  RESULT {mode}: {json.dumps(result)}")
    return result


# ---------- 4. ordering with two partitions and two Writers ----------
def ordering(mode):
    reset({TASKS: 2, DRAFTS: 1}, [f"{PREFIX}-writer"])
    a = Agents("ordering", mode)
    for i in ("1", "2"):
        a.start("writer.py", f"writer{i}", "--mock", "0", "--instance", i)
    end = time.time() + 60  # wait until the group settles with one partition per Writer
    while time.time() < end:
        last = [[e for e in a.events(f"writer{i}") if e["event"] == "partitions assigned"] for i in ("1", "2")]
        if all(last) and sorted(last[0][-1]["partitions"] + last[1][-1]["partitions"]) == [0, 1] \
                and all(len(x[-1]["partitions"]) == 1 for x in last):
            break
        time.sleep(0.5)
    time.sleep(2)

    rng = random.Random(VERIFY_SEED)
    entities = ["L-6758-001", "L-6758-002", "L-6758-003"]
    seq = dict.fromkeys(entities, 0)
    messages = []
    for i in range(20):
        e = rng.choice(entities)
        seq[e] += 1
        messages.append({"correlation_id": f"ord-{mode}-{i:02d}", "entity_id": e, "seq": seq[e], "sent_index": i,
                         "work_ms": rng.randint(50, 600), "question": f"Update {seq[e]} for listing {e}",
                         "plan": ["Apply the update", "Confirm"]})
    random.seed(VERIFY_SEED)  # the producer picks a random partition for messages without a key
    key = (lambda m: None) if mode == "before" else (lambda m: m["entity_id"])
    placed = produce(TASKS, [(m, key(m), None) for m in messages])
    say(f"  sent 20 messages ({'no key' if mode == 'before' else 'key = entity_id'}); "
        f"partitions: {[p for p, _ in placed]}")

    end = time.time() + 90
    while time.time() < end:
        done = [e for i in ("1", "2") for e in a.events(f"writer{i}") if e["event"].startswith("sent to")]
        if len(done) >= 20:
            break
        time.sleep(0.5)
    a.stop_all()

    rows = []
    for i in ("1", "2"):
        recv = {e["correlation_id"]: e for e in a.events(f"writer{i}") if e["event"].startswith("received")}
        for e in a.events(f"writer{i}"):
            if e["event"].startswith("sent to"):
                r = recv[e["correlation_id"]]
                rows.append({"finished_at": e["ts"], "writer": f"WRITER-{i}", "partition": r["partition"],
                             "offset": r["offset"], "entity_id": r["entity_id"], "seq": r["seq"],
                             "correlation_id": e["correlation_id"]})
    rows.sort(key=lambda r: r["finished_at"])
    for n, r in enumerate(rows, 1):
        r["processed_order"] = n
    with (RAW / f"part3_ordering_{mode}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["processed_order", "finished_at", "writer", "partition", "offset",
                                          "entity_id", "seq", "correlation_id"])
        w.writeheader()
        w.writerows(rows)

    per_entity = {}
    for e in entities:
        order = [r["seq"] for r in rows if r["entity_id"] == e]
        per_entity[e] = {"processed_seq": order, "in_order": order == sorted(order),
                         "inversions": sum(1 for x, y in zip(order, order[1:], strict=False) if y < x),
                         "partitions": sorted({r["partition"] for r in rows if r["entity_id"] == e})}
    for e, v in per_entity.items():
        say(f"    {e}: partitions={v['partitions']} processed seq={v['processed_seq']} in_order={v['in_order']}")
    result = {"processed": len(rows), "per_entity": per_entity,
              "entities_out_of_order": sum(1 for v in per_entity.values() if not v["in_order"])}
    say(f"  RESULT {mode}: processed={len(rows)} entities_out_of_order={result['entities_out_of_order']}")
    return result


TESTS = {"duplicate": duplicate, "consumer_death": consumer_death, "poison": poison, "ordering": ordering}


def main():
    names = list(TESTS) if sys.argv[1:] in ([], ["all"]) else sys.argv[1:]
    results_path = RAW / "part3_results.json"
    results = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
    for name in names:
        results[name] = {}
        for mode in ("before", "after"):
            say(f"\n=== {name} - {mode} fix ===")
            results[name][mode] = TESTS[name](mode)
            results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
