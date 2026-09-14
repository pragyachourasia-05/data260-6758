import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.model_client import ModelClient
from state import AgentState
from workflow import build_graph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="1400 Sq Ft 2BR Apartment Near Downtown San Jose")
    ap.add_argument("--content", default=(
        "Bright 2 bedroom, 1 bath apartment on the second floor, updated kitchen "
        "with new appliances, in-unit laundry, one covered parking spot, small "
        "balcony, walking distance to light rail. No smoking. Cats allowed with "
        "deposit."
    ))
    ap.add_argument("--email", default="pragya.chourasia@sjsu.edu")
    ap.add_argument("--model", default=os.environ.get("SMOL_MODEL", "qwen3:8b"))
    ap.add_argument("--base_url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    ap.add_argument("--strict", action="store_true")
    ap.add_argument(
        "--force_issue", action="store_true",
        help="Test hook: force the Reviewer to always report an issue, to verify the self-correction loop.",
    )
    ap.add_argument(
        "--validation_ceiling", type=int, default=3,
        help="Max Planner retries allowed after schema validation failures (Part 4c compares 2 vs 10).",
    )
    args = ap.parse_args()

    client = ModelClient(model=args.model, base_url=args.base_url, temperature=0.0)
    graph = build_graph()

    initial_state: AgentState = {
        "title": args.title,
        "content": args.content,
        "email": args.email,
        "strict": args.strict,
        "task": "",
        "client": client,
        "planner_proposal": {},
        "reviewer_feedback": {},
        "turn_count": 0,
        "force_issue": args.force_issue,
        "validation_error": "",
        "validation_attempts": 0,
        "validation_ceiling": args.validation_ceiling,
    }

    print(f"Running graph on: {args.title}")
    print(f"force_issue={args.force_issue}\n")

    final_state = None
    for step in graph.stream(initial_state):
        for node_name, update in step.items():
            printable = {k: v for k, v in update.items() if k != "client"}
            print(f"\n=== state update after '{node_name}' ===")
            print(json.dumps(printable, indent=2, default=str))
            final_state = update

    print("\n===== Cumulative model stats =====")
    print(json.dumps(client.stats([]), indent=2))


if __name__ == "__main__":
    main()
