"""HW10 driver: trace examples (Part 4.2) and the 50 cache-miss latency run (Part 4.3).

Start the three agents and evaluation/evaluator.py first, then:
    python backend/run_hw10.py examples      cache miss -> cache hit (same question) -> failed request
    python backend/run_hw10.py latency       50 new questions, each confirmed a cache miss
    python backend/run_hw10.py report        p50/p95 per stage from the saved spans

Each request waits for its evaluation span before the next one starts, so the judge never runs at the same time
as the agents.
"""
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# the sender's journey log goes to HW10, not the HW8 default file
os.environ.setdefault("HW8_LOG", str(ROOT / "reports" / "hw10" / "raw" / "journey_sender.jsonl"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "kafka_agents"))
sys.stdout.reconfigure(encoding="utf-8")

from send_question import ask  # noqa: E402

from app.semantic_cache import SemanticCache, answer_question  # noqa: E402
from observability.tracing import load_spans, write_span  # noqa: E402

RAW = ROOT / "reports" / "hw10" / "raw"
THRESHOLD = 0.95  # the threshold I chose in HW9 Part 3.4
EXAMPLE_QUESTION = "How many units are available at 135 Research Avenue, and what is the rent there?"

LATENCY_QUESTIONS = [
    "What is the monthly rent at 140 Research Avenue?",
    "Is 141 Research Avenue a house or an apartment?",
    "How many units can I rent at 142 Research Avenue right now?",
    "If I rent 143 Research Avenue for a year, what is the total cost?",
    "Which is cheaper per month, 144 Research Avenue or 145 Research Avenue?",
    "Tell me everything the listing says about 146 Research Avenue.",
    "Would 147 Research Avenue suit a family that wants a house?",
    "How much would two roommates each pay at 148 Research Avenue?",
    "Is there any vacancy at 149 Research Avenue?",
    "Can you compare the property types of 150 and 151 Research Avenue?",
    "What credit score do landlords usually look for?",
    "How do I get my security deposit back when I move out?",
    "What should I photograph during a move-in inspection?",
    "Is it a good idea to pay rent with a credit card?",
    "What is a guarantor on a lease?",
    "How does subletting an apartment work?",
    "Who pays for repairs when the heater breaks in a rental?",
    "What questions should I ask a landlord on a viewing?",
    "How can I spot a rental listing scam?",
    "Can a landlord refuse to rent to someone with a pet?",
    "What does a pro-rated first month of rent mean?",
    "How early should I start searching for an apartment near SJSU?",
    "What is the difference between a lease and a rental agreement?",
    "Can I break my lease early if I get a job in another city?",
    "How much income do I need to qualify for a $2,500 apartment?",
    "What is a holding deposit and is it refundable?",
    "Are application fees refundable if I am not approved?",
    "What utilities do renters usually pay themselves?",
    "How do I split utility bills fairly with roommates?",
    "What should a roommate agreement include?",
    "How do I report mold in my apartment?",
    "What is normal wear and tear when moving out?",
    "Can my landlord keep my deposit for carpet cleaning?",
    "Is parking usually included in apartment rent in San Jose?",
    "What happens if I pay rent a few days late?",
    "How do I write a request for a repair to my landlord?",
    "What does a month-to-month tenancy mean for notice periods?",
    "How can international students rent without a US credit history?",
    "What are the pros and cons of renting a furnished unit?",
    "Should I get renters insurance if my roommate already has it?",
    "How do I negotiate a lower rent with a landlord?",
    "What does it mean when a listing says utilities included?",
    "How often can a landlord do inspections?",
    "What can I do if my landlord will not return my calls?",
    "Is it worth paying for a moving company for a one-bedroom?",
    "What is a co-signer and how is it different from a guarantor?",
    "How do I check a landlord's reviews before signing?",
    "What fees are common besides rent when moving in?",
    "Can a landlord enter without notice in an emergency?",
    "How do I end a lease on good terms with my landlord?",
]


def agent(question: str, context: str, trace_id: str | None = None, timeout: float = 900, fail_stage=None):
    return asyncio.run(ask(question, context, correlation_id=trace_id, timeout=timeout, fail_stage=fail_stage))


def wait_for_evaluation(trace_id: str, limit_s: float = 900) -> dict | None:
    end = time.time() + limit_s
    while time.time() < end:
        found = [s for s in load_spans() if s["trace_id"] == trace_id and s["stage"] == "evaluation"]
        if found:
            return found[-1]
        time.sleep(2)
    return None


def run_one(cache: SemanticCache, question: str, label: str, fail_stage: str | None = None, timeout: float = 900) -> dict:
    trace_id = str(uuid.uuid4())
    t0 = time.time()

    def call(q, c, trace_id=None):
        return agent(q, c, trace_id, timeout=timeout, fail_stage=fail_stage)

    result = answer_question(cache, question, call, trace_id=trace_id)
    ok = result["is_cached"] or result["status"] in ("approved", "rejected")
    write_span(trace_id, "request", t0, time.time(), "ok" if ok else "error",
               None if ok else f"no final message ({result['status']})", label=label, cache="hit" if result["is_cached"] else "miss")
    evaluation = None if result["is_cached"] else wait_for_evaluation(trace_id, 400 if fail_stage else 900)
    row = {"label": label, "trace_id": trace_id, "question": question, "is_cached": result["is_cached"],
           "similarity": result["similarity"], "status": result["status"], "latency_ms": result["latency_ms"],
           "evaluation_status": evaluation["status"] if evaluation else None,
           "evaluation_error": evaluation["error"] if evaluation else None}
    print(json.dumps(row), flush=True)
    return row


def examples():
    cache = SemanticCache(threshold=THRESHOLD)
    rows = [run_one(cache, EXAMPLE_QUESTION, "cache_miss"),
            run_one(cache, EXAMPLE_QUESTION, "cache_hit"),
            run_one(cache, "What is the monthly rent at 139 Research Avenue, and is it a house?", "failed",
                    fail_stage="writer", timeout=120)]
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "trace_examples.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


def failed():
    """Rerun only the failed-request example and replace it in trace_examples.json."""
    cache = SemanticCache(threshold=THRESHOLD)
    row = run_one(cache, "Could a student on a part-time income afford 157 Research Avenue?", "failed",
                  fail_stage="writer", timeout=120)
    path = RAW / "trace_examples.json"
    rows = [r for r in json.loads(path.read_text(encoding="utf-8")) if r["label"] != "failed"] + [row]
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def latency():
    cache = SemanticCache(threshold=THRESHOLD)
    out = RAW / "latency_run.json"
    rows = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    done = {r["question"] for r in rows}
    for n, question in enumerate(LATENCY_QUESTIONS, 1):
        if question in done:
            continue
        row = run_one(cache, question, f"latency_{n:02d}")
        rows.append(row)
        out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"{n}/{len(LATENCY_QUESTIONS)} cached={row['is_cached']} status={row['status']} eval={row['evaluation_status']}", flush=True)


def percentile(values: list[float], p: float) -> float:
    v = sorted(values)
    k = (len(v) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def report():
    rows = json.loads((RAW / "latency_run.json").read_text(encoding="utf-8"))
    by_trace: dict[str, list[dict]] = {}
    for s in load_spans():
        by_trace.setdefault(s["trace_id"], []).append(s)
    queues = ("queue:s6758_inbox", "queue:s6758_tasks", "queue:s6758_drafts", "queue:s6758_final")
    stages = {"Cache lookup": ["cache_lookup"], "Planner": ["planner"], "Writer": ["writer"], "Reviewer": ["reviewer"],
              "Queue wait (total)": list(queues), "Evaluation": ["evaluation"]}
    values = {k: [] for k in stages}
    e2e, hits, bad = [], [r for r in rows if r["is_cached"]], []
    for r in rows:
        spans = by_trace.get(r["trace_id"], [])
        if r["is_cached"] or not spans:
            bad.append(r["trace_id"])
            continue
        lookup = [s for s in spans if s["stage"] == "cache_lookup"]
        evals = [s for s in spans if s["stage"] == "evaluation"]
        if not lookup or not evals or lookup[0].get("cache") != "miss":
            bad.append(r["trace_id"])
            continue
        e2e.append((evals[-1]["end_ts"] - lookup[0]["start_ts"]) * 1000)
        for name, keys in stages.items():
            values[name].append(sum(s["duration_ms"] for s in spans if s["stage"] in keys))
    total = sum(e2e)
    table = [{"stage": name, "p50_ms": round(percentile(v, 0.5), 1), "p95_ms": round(percentile(v, 0.95), 1),
              "pct_of_e2e": round(100 * sum(v) / total, 1)} for name, v in values.items()]
    summary = {"requests": len(rows), "confirmed_misses": len(e2e), "served_from_cache": len(hits), "excluded": bad,
               "e2e_p50_ms": round(percentile(e2e, 0.5), 1), "e2e_p95_ms": round(percentile(e2e, 0.95), 1),
               "table": table, "e2e_definition": "cache_lookup start -> evaluation end, per trace",
               "pct_definition": "sum of the stage over all traces / sum of end-to-end over all traces"}
    (RAW / "latency_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"confirmed misses {len(e2e)}/{len(rows)}, served from cache {len(hits)}")
    print(f"{'Stage':22}{'p50 (ms)':>12}{'p95 (ms)':>12}{'% of e2e':>10}")
    for t in table:
        print(f"{t['stage']:22}{t['p50_ms']:>12.1f}{t['p95_ms']:>12.1f}{t['pct_of_e2e']:>9.1f}%")
    print(f"{'End-to-end':22}{summary['e2e_p50_ms']:>12.1f}{summary['e2e_p95_ms']:>12.1f}")


if __name__ == "__main__":
    {"examples": examples, "failed": failed, "latency": latency, "report": report}[sys.argv[1]]()
