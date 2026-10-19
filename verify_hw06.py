"""HW6 smoke checks; run from the repository root with MongoDB, Ollama and the backend (port 8458) up.

    python verify_hw06.py        (or: make verify-hw06)

Checks behaviour, not wording, and writes reports/hw06/verification.json. It only
creates (and then deletes) a temporary listing and one chat turn for a verify user;
it never modifies application code.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports" / "hw06"
RAW = REPORTS / "raw"
BASE = "http://127.0.0.1:8458"
SID4 = 6758
VERIFY_SEED = 260000 + SID4


def http(method: str, path: str, body: dict | None = None, content_type: str = "application/json"):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else None)


def check(name: str, fn) -> dict:
    try:
        detail = fn()
        return {"name": name, "passed": True, "detail": detail or "ok"}
    except Exception as exc:  # each check reports its own failure
        return {"name": name, "passed": False, "detail": f"{type(exc).__name__}: {exc}"}


def expect(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def backend_health():
    status, body = http("GET", "/health")
    expect(status == 200 and body.get("mongo_ok") is True, f"health {status} {body}")
    return f"port 8458 up, mongo_ok={body['mongo_ok']}"


def listings_crud():
    payload = {"title": f"verify listing {VERIFY_SEED}", "property_type": "studio", "available_from": "2026-12-01T00:00:00Z"}
    status, created = http("POST", "/api/listings", payload)
    expect(status == 201 and created["status"] == "available", f"create {status}")
    lid = created["id"]
    status, _ = http("GET", f"/api/listings/{lid}")
    expect(status == 200, f"get {status}")
    status, updated = http("PUT", f"/api/listings/{lid}", {"status": "pending"})
    expect(status == 200 and updated["status"] == "pending" and updated["updated_at"] >= created["updated_at"], f"update {status}")
    status, items = http("GET", "/api/listings")
    expect(status == 200 and any(i["id"] == lid for i in items), "list missing new id")
    status, _ = http("DELETE", f"/api/listings/{lid}")
    expect(status == 204, f"delete {status}")
    status, _ = http("GET", f"/api/listings/{lid}")
    expect(status == 404, f"get after delete {status}")
    return "201 -> 200 -> 200 -> 200 -> 204 -> 404"


def listings_validation():
    codes = [
        http("POST", "/api/listings", {"property_type": "studio", "available_from": "2026-12-01"})[0],
        http("POST", "/api/listings", {"title": "x", "property_type": "castle", "available_from": "2026-12-01"})[0],
        http("POST", "/api/listings", {"title": "x", "property_type": "studio", "available_from": "soon"})[0],
        http("POST", "/api/listings", {"title": "x" * 101, "property_type": "studio", "available_from": "2026-12-01"})[0],
        http("GET", "/api/listings/not-an-id")[0],
    ]
    expect(codes == [422, 422, 422, 422, 400], f"got {codes}")
    return f"missing/enum/date/length/id -> {codes}"


def chat_turn():
    status, body = http("POST", "/api/chat", {"user_id": f"verify_{VERIFY_SEED}", "message": "My budget is $2,500 a month."})
    expect(status == 200 and body["reply"].strip(), f"chat {status}")
    used = body["memory_used"]
    expect({"short_term_count", "long_term_summary", "episodic_facts"} <= set(used), f"memory_used keys {list(used)}")
    expect(body["usage"]["prompt_tokens"] > 0, "no prompt tokens reported")
    return f"reply {len(body['reply'])} chars, prompt_tokens={body['usage']['prompt_tokens']}"


def memory_endpoints():
    s1, mem = http("GET", f"/api/memory/verify_{VERIFY_SEED}")
    s2, agg = http("GET", f"/api/aggregate/verify_{VERIFY_SEED}")
    expect(s1 == 200 and len(mem["recent_messages"]) >= 2, f"memory {s1}")
    expect(s2 == 200 and agg["daily_message_counts"], f"aggregate {s2}")
    return f"memory messages={len(mem['recent_messages'])}, aggregate days={len(agg['daily_message_counts'])}"


def part3_outputs():
    probes = yaml.safe_load((REPORTS / "memory_probes.yaml").read_text(encoding="utf-8"))["probes"]
    expect(len(probes) == 5, f"{len(probes)} probes")
    summary = json.loads((RAW / "part3_summary.json").read_text(encoding="utf-8"))
    settings = {r["setting"] for r in summary["table"]}
    expect(settings == {"n4", "n12", "n30", "n30_compress"}, f"settings {settings}")
    expect((RAW / "part3_turns.csv").exists() and (RAW / "part3_policy_comparison.json").exists(), "raw files missing")
    return f"settings={sorted(settings)}"


def file_memory_tests():
    run = subprocess.run([sys.executable, "-m", "pytest", "tests/test_file_memory.py", "-q", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True)
    expect(run.returncode == 0, run.stdout[-300:])
    return run.stdout.strip().splitlines()[-1]


def consolidation_files():
    original = (REPORTS / "memory" / "MEMORY_original.md").read_text(encoding="utf-8").splitlines()
    consolidated = (REPORTS / "memory" / "MEMORY_consolidated.md").read_text(encoding="utf-8").splitlines()
    expect(len(original) == 55 and len(consolidated) < 40, f"{len(original)} -> {len(consolidated)} lines")
    return f"{len(original)} -> {len(consolidated)} lines"


def agent_md_rules():
    run = subprocess.run([sys.executable, "code/check_agent_md_rules.py"], cwd=ROOT, capture_output=True, text=True)
    expect(run.returncode == 0, run.stdout[-300:])
    return run.stdout.strip().splitlines()[-1]


def main() -> int:
    checks = [
        check("backend_health_port_8458", backend_health),
        check("listings_crud", listings_crud),
        check("listings_validation", listings_validation),
        check("post_api_chat", chat_turn),
        check("memory_and_aggregate_endpoints", memory_endpoints),
        check("part3_raw_outputs", part3_outputs),
        check("file_memory_tests", file_memory_tests),
        check("memory_consolidation_files", consolidation_files),
        check("generated_function_follows_agent_md", agent_md_rules),
    ]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = "unknown"
    result = {
        "homework": "HW6",
        "sid4": str(SID4),
        "commit_hash": commit,
        "model_configuration": {"model": "llama3.2:3b (Ollama)", "temperature": 0.0, "num_ctx": 8192,
                                "SHORT_TERM_N": 12, "SUMMARIZE_EVERY_USER_MSGS": 4, "EPISODIC_TOP_K": 3,
                                "embedding": "local feature hashing, 512 dims", "mongo_db": "s6758_doc"},
        "seed": SID4,
        "verify_seed": VERIFY_SEED,
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
