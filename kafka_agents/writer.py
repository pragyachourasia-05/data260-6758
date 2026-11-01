"""Writer: reads a plan from s6758_tasks, writes a draft answer to s6758_drafts.

    python writer.py
    python writer.py --instance 2      second Writer in the same consumer group
"""
import asyncio
import time

from common import DRAFTS, OPTS, TASKS, llm, log, run_agent

SYSTEM = (
    "You are the Writer for a rental housing listings assistant. Answer the question by following "
    "the plan step by step. Be practical and specific, plain text, at most 150 words."
)
NAME = f"WRITER-{OPTS.instance}" if OPTS.instance else "WRITER"


def handle(message: dict) -> dict:
    steps = message["plan"]
    if not isinstance(steps, list) or not steps:
        raise ValueError("plan must be a non-empty list of steps")
    if OPTS.mock is not None:
        time.sleep(message.get("work_ms", OPTS.mock * 1000) / 1000)
        draft = f"Draft for: {message['question']}"
    else:
        plan = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
        draft = llm(SYSTEM, f"Question: {message['question']}\n\nPlan:\n{plan}")
    log(NAME, "draft ready", correlation_id=message.get("correlation_id"), words=len(draft.split()))
    out = {"question": message["question"], "plan": steps, "draft": draft}
    out.update({k: message[k] for k in ("entity_id", "seq") if k in message})
    return out


if __name__ == "__main__":
    asyncio.run(run_agent("WRITER", TASKS, DRAFTS, handle))
