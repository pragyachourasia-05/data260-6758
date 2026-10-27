"""Reviewer: reads a draft from s6758_drafts, writes the approved result to s6758_final.

    python reviewer.py
"""
import asyncio
import json

from common import DRAFTS, FINAL, llm, log, run_agent

SYSTEM = (
    "You are the Reviewer for a rental housing listings assistant. Check that the draft answers the "
    "question, follows the plan, and gives no unsafe or made-up advice. "
    'Reply only with JSON: {"approved": true or false, "notes": "one short sentence"}'
)


def review(message: dict) -> tuple[bool, str]:
    prompt = (f"Question: {message['question']}\nPlan: {json.dumps(message['plan'])}\n\nDraft:\n{message['draft']}")
    try:
        verdict = json.loads(llm(SYSTEM, prompt, as_json=True))
        return bool(verdict.get("approved")), str(verdict.get("notes", "")).strip()
    except (json.JSONDecodeError, AttributeError):
        return False, "review output was not valid JSON"


def handle(message: dict) -> dict:
    approved, notes = review(message)
    if not message.get("draft", "").strip():
        approved, notes = False, "empty draft"
    status = "approved" if approved else "rejected"
    log("REVIEWER", "review done", correlation_id=message.get("correlation_id"), status=status, notes=notes)
    return {"status": status, "answer": message["draft"], "review_notes": notes, "question": message["question"]}


if __name__ == "__main__":
    asyncio.run(run_agent("REVIEWER", DRAFTS, FINAL, handle))
