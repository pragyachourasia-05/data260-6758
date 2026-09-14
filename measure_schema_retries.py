import argparse
import contextlib
import io
import json
import os
import time
from pathlib import Path

from src.model_client import ModelClient
from state import AgentState
from workflow import build_graph


def classify(final_state):
    attempts = int(final_state.get("validation_attempts", 0))
    error = final_state.get("validation_error", "")

    if error:
        return "abandoned at ceiling"

    if attempts == 0:
        return "valid first attempt"

    if attempts == 1:
        return "valid after one retry"

    return "valid after two or more retries"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--model", default=os.environ.get("SMOL_MODEL", "llama3.2:3b"))
    parser.add_argument("--base_url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    parser.add_argument("--validation_ceiling", type=int, default=3)
    parser.add_argument(
        "--input",
        default="reports/hw02/cases/schema_input.json",
    )
    parser.add_argument(
        "--output",
        default="reports/hw02/raw/schema_validation_results.json",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frozen_input = json.loads(input_path.read_text(encoding="utf-8"))
    graph = build_graph()
    results = []

    for run_number in range(1, args.runs + 1):
        client = ModelClient(
            model=args.model,
            base_url=args.base_url,
            temperature=0.0,
        )

        initial_state: AgentState = {
            "title": frozen_input["title"],
            "content": frozen_input["content"],
            "email": frozen_input["email"],
            "strict": True,
            "task": "",
            "client": client,
            "planner_proposal": {},
            "reviewer_feedback": {},
            "turn_count": 0,
            "force_issue": False,
            "validation_error": "",
            "validation_attempts": 0,
            "validation_ceiling": args.validation_ceiling,
        }

        captured_output = io.StringIO()
        start = time.perf_counter()

        with contextlib.redirect_stdout(captured_output):
            final_state = graph.invoke(initial_state)

        latency_ms = round((time.perf_counter() - start) * 1000)

        result = {
            "run": run_number,
            "model": args.model,
            "validation_ceiling": args.validation_ceiling,
            "classification": classify(final_state),
            "validation_attempts": final_state.get("validation_attempts", 0),
            "validation_error": final_state.get("validation_error", ""),
            "turn_count": final_state.get("turn_count", 0),
            "latency_ms": latency_ms,
            "planner_proposal": final_state.get("planner_proposal", {}),
            "reviewer_feedback": final_state.get("reviewer_feedback", {}),
        }

        results.append(result)
        print(
            f"Run {run_number:02d}/{args.runs}: "
            f"{result['classification']} | "
            f"attempts={result['validation_attempts']} | "
            f"latency={latency_ms} ms"
        )

    output_path.write_text(
        json.dumps(
            {
                "experiment": "Part 4b schema-validation retries",
                "input_file": str(input_path),
                "runs": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    counts = {}
    for result in results:
        label = result["classification"]
        counts[label] = counts.get(label, 0) + 1

    print("\nResults:")
    print(json.dumps(counts, indent=2))
    print(f"\nWrote {len(results)} results to {output_path}")


if __name__ == "__main__":
    main()