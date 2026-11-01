"""HW8 smoke checks; run from the repository root with the Kafka stack up.

    python verify_hw08.py        (or: make verify-hw08)

Checks behaviour, not wording, and writes reports/hw08/verification.json. The pipeline check runs the agents
in --mock mode with temporary log and state files; application code is not modified.
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "kafka_agents"))
from failure_tests import produce, read_topic  # noqa: E402

REPORTS = ROOT / "reports" / "hw08"
RAW = REPORTS / "raw"
API = "http://127.0.0.1:8458"
SID4 = 6758
VERIFY_SEED = 260000 + SID4
LISTING = {"property_address": f"{VERIFY_SEED} Verify St, San Jose, CA", "monthly_rent": 1500,
           "property_category": "Studio", "listing_description": "verify_hw08 temporary listing"}
TOPICS = {"s6758_listing_requests": 1, "s6758_listing_responses": 1, "s6758_inbox": 1, "s6758_tasks": 2,
          "s6758_drafts": 1, "s6758_final": 1, "s6758_dead_letter": 1}


def check(name, fn):
    try:
        return {"name": name, "passed": True, "detail": fn() or "ok"}
    except Exception as exc:  # each check reports its own failure
        return {"name": name, "passed": False, "detail": f"{type(exc).__name__}: {exc}"}


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def call(operation, data, cid=None):
    cid = cid or str(uuid.uuid4())
    r = requests.post(f"{API}/kafka/listings", json={"correlation_id": cid, "operation": operation, "data": data},
                      timeout=30).json()
    expect(r.get("correlation_id") == cid, f"{operation}: correlation_id changed")
    return r


def containers_check():
    names = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    missing = {"s6758_kafka", "s6758_listing_worker", "s6758_listing_api"} - set(names)
    expect(not missing, f"not running: {missing}")
    return "Kafka, worker and FastAPI containers running"


def topics_check():
    wrong = []
    for topic, parts in TOPICS.items():
        out = subprocess.run(["docker", "exec", "s6758_kafka", "/opt/kafka/bin/kafka-topics.sh", "--bootstrap-server",
                              "localhost:9092", "--describe", "--topic", topic], capture_output=True, text=True).stdout
        if f"PartitionCount: {parts}" not in out:
            wrong.append(topic)
    expect(not wrong, f"missing or wrong partition count: {wrong}")
    return f"{len(TOPICS)} topics exist, s6758_tasks has 2 partitions"


def round_trip_check():
    created = call("CREATE_LISTING", LISTING)
    expect(created["success"] is True and created.get("listing_id"), f"create: {created}")
    fetched = call("GET_LISTING", {"listing_id": created["listing_id"]})
    expect(fetched["success"] is True, f"get: {fetched}")
    expect(all(fetched["listing"].get(k) == v for k, v in LISTING.items()), "stored fields differ")
    return "CREATE_LISTING then GET_LISTING round trip through Kafka, correlation_id preserved"


def errors_check():
    results = [call("GET_LISTING", {"listing_id": str(uuid.uuid4())}), call("CREATE_LISTING", {**LISTING, "monthly_rent": -1}),
               call("CREATE_LISTING", {**LISTING, "property_address": ""}), call("UNKNOWN_OP", {})]
    expect(all(r["success"] is False and r.get("error") for r in results), f"errors: {results}")
    return "not found, invalid rent, empty field and unknown operation all return clean errors"


def pipeline_check():
    temp = Path(tempfile.mkdtemp(prefix="verify_hw08_"))
    env = {**os.environ, "HW8_STATE": str(temp / "state.sqlite"), "PYTHONIOENCODING": "utf-8"}
    procs = []
    for agent in ("planner", "writer", "reviewer"):
        log = temp / f"{agent}.jsonl"
        procs.append(subprocess.Popen([sys.executable, "-u", f"{agent}.py", "--mock", "0.1"], cwd=ROOT / "kafka_agents",
                                      env={**env, "HW8_LOG": str(log)}, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL))
    try:
        end = time.time() + 60
        while time.time() < end:
            logs = [temp / f"{a}.jsonl" for a in ("planner", "writer", "reviewer")]
            if all(p.exists() and "partitions assigned" in p.read_text(encoding="utf-8") for p in logs):
                break
            time.sleep(0.5)
        cid = f"verify-{uuid.uuid4().hex[:8]}"
        message = {"correlation_id": cid, "question": "verify_hw08 question"}
        produce("s6758_inbox", [(message, cid, None)])
        finals = []
        end = time.time() + 45
        while time.time() < end and not finals:
            finals = [m for m in read_topic("s6758_final") if m.get("correlation_id") == cid]
        expect(finals, "no result on s6758_final")
        expect(finals[0].get("status") and finals[0].get("answer"), "final message needs status and answer")
        produce("s6758_inbox", [(message, cid, None)])  # replay
        time.sleep(5)
        count = sum(1 for m in read_topic("s6758_final") if m.get("correlation_id") == cid)
        expect(count == 1, f"replay produced {count} final messages")
        return "inbox -> final journey keeps correlation_id, replay causes no second final message"
    finally:
        for p in procs:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)


def artifacts_check():
    r = json.loads((RAW / "part3_results.json").read_text(encoding="utf-8"))
    expect(r["duplicate"]["after"]["messages_in_final"] == 1, "duplicate after fix")
    expect(r["consumer_death"]["after"]["redelivered_after_restart"] is True, "consumer death after fix")
    expect(r["poison"]["after"]["dead_letter_messages"] == 1 and r["poison"]["after"]["good_message_processed"], "poison")
    expect(r["ordering"]["after"]["entities_out_of_order"] == 0, "ordering after fix")
    for mode in ("before", "after"):
        with (RAW / f"part3_ordering_{mode}.csv").open(encoding="utf-8") as f:
            expect(len(list(csv.DictReader(f))) == 20, f"ordering {mode} needs 20 rows")
    return "failure-test results and both 20-message ordering runs present"


def main() -> int:
    checks = [check("kafka_worker_api_containers", containers_check),
              check("api_health_port_8458", lambda: requests.get(f"{API}/health", timeout=10).json()["status"]),
              check("topics_and_partitions", topics_check),
              check("create_get_round_trip", round_trip_check),
              check("clean_errors_keep_correlation_id", errors_check),
              check("agent_pipeline_and_replay", pipeline_check),
              check("raw_artifacts_present", artifacts_check)]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = {"homework": "HW8", "sid4": str(SID4), "commit_hash": commit,
              "model_configuration": {"part2_agents": "llama3.2:3b via src/model_client.ModelClient, temperature 0, seed 6758",
                                      "smoke_test_and_failure_tests": "agents in --mock mode, no LLM call",
                                      "kafka": "apache/kafka:3.9.2, single node"},
              "seed": SID4, "verify_seed": VERIFY_SEED, "checks": checks,
              "passed": all(c["passed"] for c in checks)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
