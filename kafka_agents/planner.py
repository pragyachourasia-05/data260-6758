"""Planner: reads a question from s6758_inbox, writes a plan to s6758_tasks.

    python planner.py
"""
import asyncio
import json
import re
import time

from common import INBOX, OPTS, TASKS, llm, log, run_agent

SYSTEM = (
    "You are the Planner for a rental housing listings assistant. Break the user's question into "
    "exactly 3 short steps that a writer should follow to answer it. "
    'Reply only with JSON: {"steps": ["step 1", "step 2", "step 3"]}'
)


def make_plan(question: str) -> list[str]:
    for attempt in range(2):
        try:
            steps = json.loads(llm(SYSTEM, question, as_json=True)).get("steps")
            if isinstance(steps, list) and steps and all(isinstance(s, str) and s.strip() for s in steps):
                return [re.sub(r"^\s*step\s*\d+\s*[:.)-]\s*", "", s, flags=re.I).strip() for s in steps[:5]]
        except (json.JSONDecodeError, AttributeError):
            pass
        log("PLANNER", "plan was not valid JSON, asking again", attempt=attempt + 1)
    return ["Identify what the question asks", "List the key facts a renter needs", "Give a short, practical answer"]


def handle(message: dict) -> dict:
    question = message["question"]
    if OPTS.mock is not None:
        time.sleep(OPTS.mock)
        steps = ["Check the lease terms", "Check the unit", "Answer briefly"]
    else:
        steps = make_plan(question)
    log("PLANNER", "plan ready", correlation_id=message.get("correlation_id"), steps=steps)
    return {"question": question, "plan": steps, "context": message.get("context", "")}


if __name__ == "__main__":
    asyncio.run(run_agent("PLANNER", INBOX, TASKS, handle))
