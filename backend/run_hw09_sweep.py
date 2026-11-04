"""HW9 Part 3 threshold sweep and stale-answer demo.

    python backend/run_hw09_sweep.py memo     run the real agents once per unique query, save answers and times
    python backend/run_hw09_sweep.py sweep    run the 40 cases at each threshold (Redis search is live, misses replay the memo)
    python backend/run_hw09_sweep.py stale    stale hit on a real record, then version-marker invalidation
    python backend/run_hw09_sweep.py show     print the saved table
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "reports" / "hw09" / "raw"
os.environ.setdefault("HW8_LOG", str(RAW / "part3_agents.jsonl"))
sys.path.insert(0, str(ROOT / "kafka_agents"))
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from send_question import ask  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.semantic_cache import SemanticCache, answer_question, find_listing, listing_context  # noqa: E402

THRESHOLDS = [0.75, 0.80, 0.85, 0.90, 0.95]
CASES = yaml.safe_load((ROOT / "cache_cases.yaml").read_text(encoding="utf-8"))
MEMO = RAW / "part3_agent_memo.json"
RESULTS = RAW / "part3_sweep.json"
STALE_QUESTION = "What is the monthly rent at 100 Research Avenue?"
STALE_ADDRESS_ID = 4


def real_agent(question: str, context: str) -> dict | None:
    return asyncio.run(ask(question, context))


def build_memo():
    RAW.mkdir(parents=True, exist_ok=True)
    memo = json.loads(MEMO.read_text(encoding="utf-8")) if MEMO.exists() else {}
    queries = list(dict.fromkeys(c["query"] for c in CASES["seeds"] + CASES["cases"]))
    for n, q in enumerate(queries, 1):
        if q in memo and memo[q]["status"] != "timeout":
            continue
        start = time.perf_counter()
        final = real_agent(q, listing_context(find_listing(q)))
        ms = (time.perf_counter() - start) * 1000
        memo[q] = {"answer": final.get("answer", "") if final else "", "status": final.get("status", "timeout") if final else "timeout",
                   "agent_ms": round(ms, 1)}
        MEMO.write_text(json.dumps(memo, indent=2), encoding="utf-8")
        print(f"{n}/{len(queries)} {memo[q]['status']} {ms / 1000:.1f}s  {q}", flush=True)


def run_sweep():
    memo = json.loads(MEMO.read_text(encoding="utf-8"))
    cache = SemanticCache()
    replay = lambda q, _context: memo[q]  # noqa: E731
    all_results = {}
    for threshold in THRESHOLDS:
        cache.threshold = threshold
        cache.clear()
        for seed in CASES["seeds"]:
            answer_question(cache, seed["query"], replay, seed["answer_key"])
        rows = []
        for case in CASES["cases"]:
            r = answer_question(cache, case["query"], replay, case["answer_key"])
            false_hit = r["is_cached"] and r["cached_key"] != case["answer_key"]
            rows.append({**{k: case[k] for k in ("id", "group", "expected", "answer_key")}, **r, "false_hit": false_hit})
        hits = sum(r["is_cached"] for r in rows)
        false_hits = sum(r["false_hit"] for r in rows)
        summary = {"threshold": threshold, "queries": len(rows), "hits": hits, "misses": len(rows) - hits, "false_hits": false_hits,
                   "hit_rate": hits / len(rows), "false_hit_rate": false_hits / len(rows),
                   "mean_latency_ms": sum(r["latency_ms"] for r in rows) / len(rows),
                   "missed_should_hit": sum(r["expected"] == "hit" and not r["is_cached"] for r in rows)}
        all_results[str(threshold)] = {"summary": summary, "rows": rows}
        print(json.dumps(summary), flush=True)
    cache.clear()
    RESULTS.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    show()


def show():
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    print(f"{'Threshold':10}{'Hit rate':10}{'False hits':12}{'False-hit rate':16}{'Missed hits':13}{'Mean latency (ms)':>18}")
    for t, d in data.items():
        s = d["summary"]
        print(f"{t:10}{s['hit_rate']:<10.0%}{s['false_hits']:<12}{s['false_hit_rate']:<16.1%}{s['missed_should_hit']:<13}{s['mean_latency_ms']:>18.1f}")


def set_rent(listing_id: int, rent: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE listings SET monthly_rent = :rent WHERE id = :id"), {"rent": rent, "id": listing_id})


def stale_demo():
    original = find_listing(STALE_QUESTION)["monthly_rent"]
    new_rent = "$1999/month"
    report = {"question": STALE_QUESTION, "listing_id": STALE_ADDRESS_ID, "original_rent": original, "new_rent": new_rent}
    cache = SemanticCache(threshold=0.85, check_version=False)
    cache.clear()
    try:
        first = answer_question(cache, STALE_QUESTION, real_agent, "rent@100")
        print(f"1. Cold cache   is_cached={first['is_cached']}  latency_ms={first['latency_ms']}\n   Answer: {first['answer'][:220]}\n", flush=True)
        set_rent(STALE_ADDRESS_ID, new_rent)
        print(f"2. UPDATE listings SET monthly_rent = '{new_rent}' WHERE id = {STALE_ADDRESS_ID} (was {original})\n", flush=True)
        stale = answer_question(cache, STALE_QUESTION, real_agent, "rent@100")
        print(f"3. Version check OFF  is_cached={stale['is_cached']}  similarity={stale['similarity']}  -> STALE HIT\n   Answer: {stale['answer'][:220]}\n", flush=True)
        cache.check_version = True
        fresh = answer_question(cache, STALE_QUESTION, real_agent, "rent@100")
        print(f"4. Version check ON   is_cached={fresh['is_cached']}  stale_dropped={fresh['stale_dropped']}  latency_ms={fresh['latency_ms']}\n   Answer: {fresh['answer'][:220]}\n", flush=True)
        again = answer_question(cache, STALE_QUESTION, real_agent, "rent@100")
        print(f"5. Asked again        is_cached={again['is_cached']}  similarity={again['similarity']}  latency_ms={again['latency_ms']}\n   Answer: {again['answer'][:220]}\n", flush=True)
        report.update(cold=first, stale_hit=stale, after_invalidation=fresh, repeat=again,
                      stale_answer_has_old_rent=original.split("/")[0] in stale["answer"],
                      fresh_answer_has_new_rent=new_rent.split("/")[0] in fresh["answer"])
    finally:
        set_rent(STALE_ADDRESS_ID, original)
        cache.clear()
        print(f"Restored listing {STALE_ADDRESS_ID} rent to {original}", flush=True)
    (RAW / "part3_stale.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    {"memo": build_memo, "sweep": run_sweep, "stale": stale_demo, "show": show}[sys.argv[1]]()
