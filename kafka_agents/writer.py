"""Writer: reads a plan from s6758_tasks, writes a draft answer to s6758_drafts.

    python writer.py
"""
import asyncio

from common import DRAFTS, TASKS, llm, log, run_agent

SYSTEM = (
    "You are the Writer for a rental housing listings assistant. Answer the question by following "
    "the plan step by step. Be practical and specific, plain text, at most 150 words."
)


def handle(message: dict) -> dict:
    plan = "\n".join(f"{i}. {s}" for i, s in enumerate(message["plan"], 1))
    draft = llm(SYSTEM, f"Question: {message['question']}\n\nPlan:\n{plan}")
    log("WRITER", "draft ready", correlation_id=message.get("correlation_id"), words=len(draft.split()))
    return {"question": message["question"], "plan": message["plan"], "draft": draft}


if __name__ == "__main__":
    asyncio.run(run_agent("WRITER", TASKS, DRAFTS, handle))
