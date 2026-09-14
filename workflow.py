from langgraph.graph import StateGraph, END

from state import AgentState
from nodes import planner_node, reviewer_node, supervisor_node
from router import router_logic


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("planner", planner_node)
    graph.add_node("reviewer", reviewer_node)

    graph.set_entry_point("supervisor")

    # The supervisor never talks to the model -- it just advances turn_count,
    # then router_logic reads the state and picks the next stop.
    graph.add_conditional_edges(
        "supervisor",
        router_logic,
        {"planner": "planner", "reviewer": "reviewer", END: END},
    )

    # Both worker nodes report back to the supervisor, which increments the
    # turn counter again before router_logic decides the next move -- this
    # is what makes the reviewer-found-an-issue loop-back possible.
    graph.add_edge("planner", "supervisor")
    graph.add_edge("reviewer", "supervisor")

    return graph.compile()
