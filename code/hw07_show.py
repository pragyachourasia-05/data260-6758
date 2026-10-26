"""Print saved HW7 outputs in the terminal.

    python code/hw07_show.py log          Part 2 tool call log
    python code/hw07_show.py reflection   Part 3 stored reflection
"""
import json
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "reports" / "hw07" / "raw"


def show_log():
    runs = json.loads((RAW / "part2_demo_runs.json").read_text(encoding="utf-8"))["runs"]
    for r in runs:
        calls = " -> ".join(f"{t['tool']}({json.dumps(t['input'])})" for t in r["trace"])
        print(f"{r['case']}: {calls}  [{r['tool_calls']} calls, stop={r['stop_reason']}]\n")


def show_reflection():
    comp = json.loads((RAW / "part3_comparison.json").read_text(encoding="utf-8"))
    run = next(r for r in comp["reflexion"] if r["success"] and r["retries"] > 0)
    for line in (RAW / "part3_reflections.jsonl").read_text(encoding="utf-8").splitlines():
        x = json.loads(line) if line.strip() else None
        if x and x["run_id"] == run["run_id"]:
            print(json.dumps({"case": x["case"], "attempt": x["attempt"],
                              "evidence": [f"{e['assertion']}: {e['detail']}" for e in x["evidence"]],
                              "reflection": x["reflection"]}, indent=1))
    print(f"\ncase {run['case']}: stop_reason={run['stop_reason']}, retries={run['retries']}")


if __name__ == "__main__":
    {"log": show_log, "reflection": show_reflection}[sys.argv[1] if len(sys.argv) > 1 else "log"]()
