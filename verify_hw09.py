"""HW9 smoke checks; run from the repository root with Redis and MySQL up.

    python verify_hw09.py        (or: make verify-hw09)

Checks behaviour, not wording, and writes reports/hw09/verification.json. It uses a throwaway counter id and
a stub agent, so no LLM runs and application code is not modified.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
from app.listing_cache import ListingCache  # noqa: E402
from app.semantic_cache import SemanticCache, answer_question  # noqa: E402

REPORTS = ROOT / "reports" / "hw09"
RAW = REPORTS / "raw"
DATA = ROOT / "self_improving_agents" / "data"
SID4 = 6758
VERIFY_SEED = 260000 + SID4
VARIANTS = {"Baseline", "Evaluator Repair", "Lesson Memory", "Validated Improvement"}


def check(name, fn):
    try:
        return {"name": name, "passed": True, "detail": fn() or "ok"}
    except Exception as exc:  # each check reports its own failure
        return {"name": name, "passed": False, "detail": f"{type(exc).__name__}: {exc}"}


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def counter_check():
    cache = ListingCache()
    key = cache.views_key(VERIFY_SEED)
    cache.redis_client.delete(key)
    try:
        synced = []
        for _ in range(25):
            count = cache.increment_listing_views(VERIFY_SEED)
            if cache.last_synced:
                synced.append(count)
        expect(count == 25 and synced == [10, 20], f"count={count} synced={synced}")
    finally:
        cache.redis_client.delete(key)
    return "25 increments, synced at 10 and 20"


def semantic_check():
    cache = SemanticCache(threshold=0.85)
    cache.clear()
    calls = []

    def agent(question, _context):
        calls.append(question)
        return {"answer": f"stub answer {VERIFY_SEED}", "status": "approved"}

    try:
        first = answer_question(cache, "How much security deposit do landlords usually charge?", agent)
        exact = answer_question(cache, "How much security deposit do landlords usually charge?", agent)
        para = answer_question(cache, "What is the typical security deposit a landlord charges?", agent)
        other = answer_question(cache, "What is the capital of Australia?", agent)
    finally:
        cache.clear()
    expect(first["is_cached"] is False and other["is_cached"] is False, "new queries must miss")
    expect(exact["is_cached"] is True and exact["similarity"] >= 0.99, f"exact: {exact}")
    expect(para["is_cached"] is True and para["similarity"] >= 0.85, f"paraphrase: {para}")
    expect(len(calls) == 2, f"agent ran {len(calls)} times, expected 2")
    return f"miss, exact hit, paraphrase hit at {para['similarity']}, unrelated miss"


def key_prefix_check():
    client = ListingCache().redis_client
    bad = [k for k in client.scan_iter("*", count=500) if not k.startswith("s6758")]
    expect(not bad, f"keys without the prefix: {bad[:5]}")
    return "every Redis key starts with s6758"


def cases_check():
    cases = yaml.safe_load((ROOT / "cache_cases.yaml").read_text(encoding="utf-8"))["cases"]
    groups = {}
    for c in cases:
        groups[c["group"]] = groups.get(c["group"], 0) + 1
    expect(len(cases) == 40 and all(n == 10 for n in groups.values()) and len(groups) == 4, f"groups={groups}")
    # the labels must be in git unchanged since the commit made before the sweep
    changed = subprocess.run(["git", "diff", "--name-only", "4c061f0", "HEAD", "--", "cache_cases.yaml"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "cache_cases.yaml"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    expect(not changed and not dirty, "cache_cases.yaml changed after the pre-sweep commit")
    return "40 cases, 10 per group, unchanged since commit 4c061f0"


def sweep_check():
    data = load(RAW / "part3_sweep.json")
    expect(set(data) == {"0.75", "0.8", "0.85", "0.9", "0.95"}, f"thresholds {list(data)}")
    expect(all(len(v["rows"]) == 40 for v in data.values()), "each threshold needs 40 rows")
    return "5 thresholds with 40 rows each"


def stale_check():
    s = load(RAW / "part3_stale.json")
    expect(s["stale_hit"]["is_cached"] and s["stale_answer_has_old_rent"], "no stale hit shown")
    expect(s["after_invalidation"]["stale_dropped"] and s["fresh_answer_has_new_rent"], "invalidation did not refresh")
    return "stale hit shown, then dropped and regenerated"


def datasets_check():
    for name in ("training_data", "validation_data", "test_data"):
        items = load(DATA / f"{name}.json")
        expect(items and all(set(x) == {"id", "question"} for x in items), f"{name} must hold only id and question")
    expect(load(DATA / "reference_data.json")["checks"], "reference checks missing")
    return "three question files hold no expected answers; reference data present"


def lessons_check():
    lessons = load(DATA / "lessons.json")
    required = {"lesson_id", "failure_pattern", "correction", "created_at", "use_count"}
    expect(lessons and all(required <= set(x) for x in lessons), "lesson fields missing")
    return f"{len(lessons)} validated lesson(s) with the required fields"


def results_check():
    results = load(RAW / "part4_test.json")
    expect(set(results) == VARIANTS, f"variants {list(results)}")
    n = len(load(DATA / "test_data.json"))
    expect(all(r["summary"]["correct"] + r["summary"]["incorrect"] == n for r in results.values()), "counts do not add up")
    expect(all(x["attempts"] <= 2 for r in results.values() for x in r["rows"]), "more than two attempts")
    demo = load(RAW / "part4_demo.json")
    expect(demo["revision"]["attempts"] == 2 and demo["revision"]["final_result"] == "PASS", "revision demo")
    expect(demo["later"]["lessons_loaded"] and demo["use_count"] >= 1, "lesson reuse demo")
    return "four variants on the test set, at most two attempts, revision and reuse demos saved"


def main() -> int:
    checks = [check("counter_syncs_every_10", counter_check),
              check("semantic_cache_hit_miss", semantic_check),
              check("redis_keys_prefixed", key_prefix_check),
              check("cache_cases_labeled_and_unchanged", cases_check),
              check("threshold_sweep_saved", sweep_check),
              check("stale_answer_invalidation", stale_check),
              check("datasets_have_no_answers", datasets_check),
              check("lessons_json_fields", lessons_check),
              check("test_results_and_demos", results_check)]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = {"homework": "HW9", "sid4": str(SID4), "commit_hash": commit,
              "model_configuration": {"agents": "llama3.2:3b via src/model_client.ModelClient, temperature 0, seed 6758",
                                      "embeddings": "sentence-transformers all-MiniLM-L6-v2, CPU, 384 dimensions, cosine",
                                      "redis": "redis/redis-stack-server:7.4.0-v3",
                                      "this_check": "stub agent, no LLM call"},
              "seed": SID4, "verify_seed": VERIFY_SEED, "checks": checks, "passed": all(c["passed"] for c in checks)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
