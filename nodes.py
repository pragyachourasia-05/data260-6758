import json
from typing import Dict, Any

from agents_demo import parse_and_coerce, extract_json_block  # reused as-is from HW1, not duplicated
from schemas import validate_planner_data
from state import AgentState

PLANNER_SYSTEM = (
    "Propose exactly 3 distinct, topical tags (prefer multi-word phrases) and a "
    "one-line summary for the rental listing."
)
REVIEWER_SYSTEM = (
    "Validate: tags topical and not generic; summary <= 25 words; no code or markdown. "
    "If issues, list in data.issues; otherwise echo cleaned tags/summary."
)


def _task_text(state: AgentState) -> str:
    return (
        f'Given rental listing title "{state["title"]}" and description "{state["content"]}", '
        f'produce exactly 3 topical tags and a one-sentence summary in your own words. '
        f'Submitter email is {state["email"]}.'
    )


def _instructions() -> str:
    return (
        "Return ONLY one JSON object (no code fences, no markdown, no explanations). "
        "Keys: thought (string), message (non-empty, <=60 words, no code), "
        "data.tags (array of exactly 3 topical tags), "
        "data.summary (<=25 words, no ellipses), data.issues (array).\n"
        "Do not add extra text outside JSON."
    )


def planner_node(state: AgentState) -> Dict[str, Any]:
    """
    Calls the model (via state['client'], the HW1 ModelClient adapter) to
    propose tags + a summary. The raw output is then strictly validated
    against schemas.PlannerOutputSchema (Part 4) -- if it fails, the
    specific validation error is stored in state so the NEXT call to this
    node includes it in the prompt, asking the model to fix that exact
    problem. router.py decides whether to retry or give up based on
    validation_ceiling.
    """
    print("---NODE: Planner---")
    task = state.get("task") or _task_text(state)

    prior_error = state.get("validation_error", "")
    retry_note = ""
    if prior_error:
        retry_note = (
            f"\n\nYour previous attempt FAILED validation with this error: {prior_error}\n"
            "Fix this specific problem and return a corrected JSON object."
        )

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM},
        {"role": "user", "content": f"Task:\n{task}\n\n{_instructions()}{retry_note}"},
    ]
    result = state["client"].complete(messages)

    # Forgiving normalization (same as HW1) -- always produces something usable downstream.
    proposal = parse_and_coerce(result["text"], state["title"], state["content"], state["strict"])

    # Separately, validate the RAW model output strictly for Part 4's retry logic.
    # This deliberately does NOT use the repaired/backfilled `proposal` above --
    # we want to know if the MODEL ITSELF produced a schema-valid reply.
    try:
        raw_obj = json.loads(extract_json_block(result["text"]))
        raw_data = raw_obj.get("data", raw_obj) if isinstance(raw_obj, dict) else {}
    except Exception:
        raw_data = {}

    is_valid, error = validate_planner_data(raw_data)

    if is_valid:
        print("    validation PASSED")
        return {
            "planner_proposal": proposal,
            "task": task,
            "reviewer_feedback": {},
            "validation_error": "",
        }

    attempts = state.get("validation_attempts", 0) + 1
    print(f"    validation FAILED (attempt {attempts}): {error}")
    return {
        "planner_proposal": proposal,  # best-effort fallback if we hit the ceiling
        "task": task,
        "reviewer_feedback": {},
        "validation_error": error,
        "validation_attempts": attempts,
    }


def reviewer_node(state: AgentState) -> Dict[str, Any]:
    """
    Reviews the Planner's current proposal. When state['force_issue'] is set
    (a test hook, not a permanent behavior), it skips the model call and
    manually reports an issue -- this is how Step 6 of the assignment
    verifies the self-correction loop actually routes back to the Planner.
    """
    print("---NODE: Reviewer---")

    if state.get("force_issue"):
        print("    (force_issue=True -- skipping model call, injecting a fake issue)")
        feedback = {
            "thought": "Test mode: forcing a validation issue to exercise the retry loop.",
            "message": "Forced issue for loop testing.",
            "data": {
                "tags": state["planner_proposal"].get("data", {}).get("tags", []),
                "summary": state["planner_proposal"].get("data", {}).get("summary", ""),
                "issues": ["forced_test_issue: tags need another pass"],
            },
        }
        return {"reviewer_feedback": feedback}

    proposal = state["planner_proposal"]
    history = f"Planner: {json.dumps(proposal)}"

    messages = [
        {"role": "system", "content": REVIEWER_SYSTEM},
        {"role": "user", "content": f"Task:\n{state['task']}\n\nConversation so far:\n{history}\n\n{_instructions()}"},
    ]
    result = state["client"].complete(messages)
    feedback = parse_and_coerce(result["text"], state["title"], state["content"], state["strict"])

    return {"reviewer_feedback": feedback}


def supervisor_node(state: AgentState) -> Dict[str, Any]:
    """
    The state-updating half of the supervisor: its only job is to advance
    turn_count. The routing decision itself lives in router.py's
    router_logic, which reads (but doesn't modify) the state.
    """
    new_count = state.get("turn_count", 0) + 1
    print(f"---NODE: Supervisor (turn {new_count})---")
    return {"turn_count": new_count}
