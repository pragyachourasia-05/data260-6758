"""HW10 Part 2: evaluator for the Planner -> Writer -> Reviewer pipeline.

    python evaluation/evaluator.py            (keep it running next to the three agents)

Reads s6758_tasks (plan), s6758_drafts (draft) and s6758_final (final answer) and joins them on correlation_id.
When all three are in, it runs the GEval judge and appends one record to reports/hw10/raw/evaluations.jsonl.
Bounded: bad JSON is skipped, every judge call has a timeout, and a request missing a message for more than
PENDING_TTL_S is closed with an error instead of waiting forever.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from aiokafka import AIOKafkaConsumer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "kafka_agents"))
from common import BOOTSTRAP, DRAFTS, FINAL, PREFIX, TASKS, log, start  # noqa: E402

from evaluation.judge import HELPFULNESS_STEPS, JUDGE_MODEL, PLAN_STEPS, metric, score  # noqa: E402
from observability.tracing import iso, queue_span, write_span  # noqa: E402

OUT = Path(os.getenv("HW10_EVALS", ROOT / "reports" / "hw10" / "raw" / "evaluations.jsonl"))
PENDING_TTL_S = float(os.getenv("EVAL_PENDING_TTL_S", "900"))
ROLE = {TASKS: "plan", DRAFTS: "draft", FINAL: "final"}


def interpret(draft: int | None, final: int | None, same_text: bool) -> str:
    if draft is None or final is None:
        return "Not comparable: one of the judge calls failed."
    diff = final - draft
    if same_text:
        return (f"No real improvement: the Reviewer approves or rejects but passes the Writer's draft through "
                f"unchanged, so the texts are identical and a difference of {diff:+d} is judge noise.")
    if diff > 0:
        return f"The final answer scored {diff} higher than the draft."
    if diff < 0:
        return f"The final answer scored {-diff} lower than the draft."
    return "Same score for draft and final."


def evaluate(cid: str, parts: dict) -> dict:
    plan_msg, draft_msg, final_msg = parts["plan"]["value"], parts["draft"]["value"], parts["final"]["value"]
    question = final_msg.get("question") or draft_msg.get("question", "")
    facts = draft_msg.get("context", "")
    steps = plan_msg.get("plan", [])
    plan_text = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1)) if isinstance(steps, list) else str(steps)
    draft, final = draft_msg.get("draft", ""), final_msg.get("answer", "")
    plan_r = score(metric("Plan Quality", PLAN_STEPS), question, plan_text, facts)
    draft_r = score(metric("Writer Helpfulness", HELPFULNESS_STEPS), question, draft, facts)
    final_r = score(metric("Final Answer Helpfulness", HELPFULNESS_STEPS), question, final, facts)
    same = draft.strip() == final.strip()
    diff = None if None in (draft_r["score"], final_r["score"]) else final_r["score"] - draft_r["score"]
    errors = [f"{k}: {r['error']}" for k, r in (("plan", plan_r), ("draft", draft_r), ("final", final_r)) if r["error"]]
    return {
        "trace_id": cid, "correlation_id": cid, "question": question, "listing_facts": facts,
        "judge": {"model": JUDGE_MODEL, "temperature": 0, "seed": 6758, "scale": "1-5"},
        "plan_quality": {"score": plan_r["score"], "reason": plan_r["reason"], "plan": steps},
        "writer_helpfulness": {"score": draft_r["score"], "reason": draft_r["reason"], "trace_id": cid},
        "final_answer_helpfulness": {"score": final_r["score"], "reason": final_r["reason"], "final_answer": final,
                                     "reviewer_status": final_msg.get("status"), "review_notes": final_msg.get("review_notes")},
        "final_vs_draft": {"draft_score": draft_r["score"], "final_score": final_r["score"], "difference": diff,
                           "same_text": same, "interpretation": interpret(draft_r["score"], final_r["score"], same)},
        "messages": {role: parts[role] for role in ("plan", "draft", "final")},  # raw content + topic/partition/offset
        "errors": errors, "evaluated_at": iso(time.time()),
    }


async def main() -> None:
    consumer = AIOKafkaConsumer(TASKS, DRAFTS, FINAL, bootstrap_servers=BOOTSTRAP, group_id=f"{PREFIX}-evaluator",
                                auto_offset_reset="latest", enable_auto_commit=True)
    await start(consumer, "EVALUATOR")
    log("EVALUATOR", f"listening on {TASKS}, {DRAFTS}, {FINAL}", judge=JUDGE_MODEL)
    pending: dict[str, dict] = {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    while True:
        batch = await consumer.getmany(timeout_ms=1000)
        for msgs in batch.values():
            for msg in msgs:
                received = time.time()
                try:
                    value = json.loads(msg.value.decode())
                    cid = value["correlation_id"]
                except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
                    log("EVALUATOR", "skipped malformed message", topic=msg.topic, offset=msg.offset, error=str(exc))
                    continue
                if msg.topic == FINAL:
                    queue_span(cid, f"{FINAL}->evaluator", value.get("sent_ts"), received)
                entry = pending.setdefault(cid, {"first_seen": received})
                entry[ROLE[msg.topic]] = {"topic": msg.topic, "partition": msg.partition, "offset": msg.offset,
                                          "kafka_timestamp_ms": msg.timestamp, "value": value}
        now = time.time()
        for cid in list(pending):
            entry = pending[cid]
            if all(r in entry for r in ("plan", "draft", "final")):
                del pending[cid]
                t0 = time.time()
                record = await asyncio.to_thread(evaluate, cid, entry)
                with OUT.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
                status = "error" if record["errors"] else "ok"
                write_span(cid, "evaluation", t0, time.time(), status, "; ".join(record["errors"]) or None,
                           plan=record["plan_quality"]["score"], draft=record["writer_helpfulness"]["score"],
                           final=record["final_answer_helpfulness"]["score"])
                log("EVALUATOR", "evaluated", correlation_id=cid, status=status,
                    scores=[record["plan_quality"]["score"], record["writer_helpfulness"]["score"],
                            record["final_answer_helpfulness"]["score"]])
            elif now - entry["first_seen"] > PENDING_TTL_S:
                del pending[cid]
                missing = [r for r in ("plan", "draft", "final") if r not in entry]
                write_span(cid, "evaluation", entry["first_seen"], now, "error", f"incomplete after {PENDING_TTL_S:.0f}s, missing {missing}")
                log("EVALUATOR", "gave up on incomplete request", correlation_id=cid, missing=missing)


if __name__ == "__main__":
    asyncio.run(main())
