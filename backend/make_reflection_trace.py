"""Print a readable step-by-step trace of one run from agent_runs.jsonl to help you
write REFLECTION.md. Usage: python backend\\make_reflection_trace.py [run_id]
(With no run_id it uses the last run in the file.)"""
import json
import sys
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "reports" / "hw05" / "raw" / "agent_runs.jsonl"
rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
run_id = sys.argv[1] if len(sys.argv) > 1 else rows[-1]["run_id"]
for r in (x for x in rows if x["run_id"] == run_id):
    t = r["type"]
    if t == "start":
        print(f"START   user_input={r['user_input']!r} max_steps={r['max_steps']}")
    elif t == "model_response":
        print(f"STEP {r['step']}  model asked for {r['n_tool_calls']} tool call(s)")
    elif t == "tool_call":
        print(f"STEP {r['step']}  tool {r['tool']} input={r['input']} -> {r['result'][:120]}")
    elif t == "final":
        print(f"FINAL   stop_reason={r['stop_reason']} steps={r['steps']} tool_calls={r['tool_calls']}")
