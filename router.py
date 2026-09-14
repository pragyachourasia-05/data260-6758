from langgraph.graph import END
from state import AgentState

DEFAULT_TURN_CEILING = 20  # generous overall safety net -- validation_ceiling is the real constraint Part 4 studies


def router_logic(state: AgentState) -> str:
    """
    Reads (never modifies) the state and decides where to go next.
    Checked in this order:
      1. Part 4 validation gate -- a schema-invalid Planner output must be
         retried (or abandoned at validation_ceiling) BEFORE ever reaching
         the Reviewer.
      2. Overall turn ceiling -- a generous safety net (default 20), kept
         separate from validation_ceiling so that Part 4c's ceiling=10 runs
         aren't cut short by this unrelated limit.
      3. Part 3 Planner/Reviewer routing -- no proposal yet -> planner;
         proposal but no feedback -> reviewer; feedback has issues -> back
         to planner; clean feedback -> END.
    """
    validation_ceiling = state.get("validation_ceiling", 3)
    turn_ceiling = state.get("turn_ceiling", DEFAULT_TURN_CEILING)

    if state.get("validation_error"):
        if state.get("validation_attempts", 0) >= validation_ceiling:
            print(f"---ROUTER: validation ceiling ({validation_ceiling}) reached -> END (abandoned)---")
            return END
        print(f"---ROUTER: validation failed (attempt {state.get('validation_attempts', 0)}) -> retry Planner---")
        return "planner"

    if state.get("turn_count", 0) >= turn_ceiling:
        print(f"---ROUTER: overall turn ceiling ({turn_ceiling}) reached -> END---")
        return END

    if not state.get("planner_proposal"):
        print("---ROUTER: no proposal yet -> Planner---")
        return "planner"

    feedback = state.get("reviewer_feedback")
    if not feedback:
        print("---ROUTER: proposal exists, no feedback yet -> Reviewer---")
        return "reviewer"

    issues = feedback.get("data", {}).get("issues", [])
    if issues:
        print(f"---ROUTER: issues found ({issues}) -> back to Planner---")
        return "planner"

    print("---ROUTER: no issues -> END---")
    return END
