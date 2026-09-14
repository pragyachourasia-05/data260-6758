from typing import TypedDict, Dict, Any


class AgentState(TypedDict):
    """
    Shared memory for the graph. Every node reads from this and returns
    only the keys it wants to update -- LangGraph merges those updates
    back into the state between steps.
    """
    title: str
    content: str
    email: str
    strict: bool
    task: str
    client: Any  # a src.model_client.ModelClient instance -- all LLM calls route through this
    planner_proposal: Dict[str, Any]
    reviewer_feedback: Dict[str, Any]
    turn_count: int
    force_issue: bool  # test hook: when True, reviewer_node always reports an issue (Step 6 of the assignment)

    # ---- Part 4: schema validation + loop safety ----
    validation_error: str        # empty string means the last Planner output passed validation
    validation_attempts: int     # number of times validation has FAILED so far for this run
    validation_ceiling: int      # max validation retries before giving up (compared: 2 vs 10)
