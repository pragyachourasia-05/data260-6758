"""HW7 Parts 2 and 3 runner.

    python backend/run_hw07_agent.py demo             # tasks A, B, C + nonexistent-id case, full tool logs
    python backend/run_hw07_agent.py reliability 21   # >= 20 tool-use attempts across A/B/C, same settings
    python backend/run_hw07_agent.py compare 3        # original loop vs Reflexion, each task N times

Raw results go to reports/hw07/raw/ (part2_*.json/csv, part3_*.json, part3_reflections.jsonl).
"""
import csv
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from agent_hw07 import MAX_REPAIRS, MAX_STEPS, MODEL, TEMPERATURE, run_agent  # noqa: E402
from reflexion_hw07 import ReflectionStore, run_reflexion, unsupported_claims, verify  # noqa: E402

RAW = ROOT / "reports" / "hw07" / "raw"
CASES = json.loads((ROOT / "reports" / "hw07" / "cases" / "agent_tasks.json").read_text(encoding="utf-8"))
SETTINGS = {"model": MODEL, "temperature": TEMPERATURE, "max_steps": MAX_STEPS, "max_repairs": MAX_REPAIRS}
FAILURE_TYPES = ["malformed_arguments", "unknown_tool", "text_instead_of_tool", "lost_chain"]


def stamp(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def demo() -> None:
    stamp(f"Part 2 demo - settings {SETTINGS}")
    out = []
    for case in CASES["cases"] + [CASES["error_case"]]:
        stamp(f"task {case['id']} ({case['title']}): {case['prompt']}")
        r = run_agent(case["prompt"], required_tools=case["required_tools"])
        print(f"  FINAL ANSWER: {r['final']}\n", flush=True)
        out.append({"case": case["id"], "prompt": case["prompt"], **{k: r[k] for k in (
            "final", "stop_reason", "tool_calls", "repairs", "failures", "tokens", "latency_ms")},
            "trace": [{"tool": t["tool"], "input": t["input"], "result": t["result"]} for t in r["trace"]]})
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part2_demo_runs.json").write_text(json.dumps({"settings": SETTINGS, "runs": out}, indent=2), encoding="utf-8")
    stamp("saved reports/hw07/raw/part2_demo_runs.json")


def reliability(n: int) -> None:
    stamp(f"Part 2 reliability - {n} attempts across A/B/C - settings {SETTINGS}")
    rows = []
    for i in range(n):
        case = CASES["cases"][i % 3]
        r = run_agent(case["prompt"], required_tools=case["required_tools"], log=lambda _m: None)
        types = [f["type"] for f in r["failures"]]
        trace = r["trace"]
        # a rejected call counts as repaired when the same tool later runs with valid arguments
        rejected = [k for k, t in enumerate(trace) if not t["ok_call"]]
        repaired = sum(1 for k in rejected if any(t["ok_call"] and t["tool"] == trace[k]["tool"] for t in trace[k + 1:]))
        executed = {t["tool"] for t in trace if t["ok_call"]}
        chain_complete = all(t in executed for t in case["required_tools"])
        ok_after = r["stop_reason"] == "completed" and chain_complete
        row = {"attempt": i + 1, "case": case["id"], "stop_reason": r["stop_reason"], "tool_calls": r["tool_calls"],
               "proposed_calls": r["proposed_calls"], "well_formed_as_proposed": r["well_formed_as_proposed"],
               "rejected_calls": len(rejected), "rejected_then_repaired": repaired, "repairs": r["repairs"],
               "no_failure_before_repair": not types, "chain_complete": chain_complete, "completed_after_repair": ok_after,
               **{t: types.count(t) for t in FAILURE_TYPES},
               "unrecovered_failure": "" if ok_after else (types[-1] if types else r["stop_reason"]),
               "tokens": r["tokens"], "latency_ms": r["latency_ms"], "verifier_passed": verify(case, r)["passed"],
               "failure_sequence": "|".join(types),
               "trace": json.dumps([{"tool": t["tool"], "input": t["input"], "ok": t["ok_call"]} for t in trace])}
        rows.append(row)
        stamp(f"attempt {i + 1:2d} case {case['id']}: stop={r['stop_reason']:13} calls={r['tool_calls']} "
              f"proposed={r['proposed_calls']} ok_as_proposed={r['well_formed_as_proposed']} failures={types}")
    calls = sum(r["proposed_calls"] for r in rows)
    summary = {
        "settings": SETTINGS, "attempts": n, "proposed_calls": calls,
        "per_call_well_formed_before_repair": round(sum(r["well_formed_as_proposed"] for r in rows) / max(calls, 1), 3),
        "per_call_well_formed_after_repair": round(sum(r["well_formed_as_proposed"] + r["rejected_then_repaired"]
                                                       for r in rows) / max(calls, 1), 3),
        "attempts_no_failure_before_repair": round(sum(r["no_failure_before_repair"] for r in rows) / n, 3),
        "attempts_completed_after_repair": round(sum(r["completed_after_repair"] for r in rows) / n, 3),
        "failure_events_by_type": {t: sum(r[t] for r in rows) for t in FAILURE_TYPES},
        "attempts_with_failure_by_type": {t: sum(1 for r in rows if r[t]) for t in FAILURE_TYPES},
        "unrecovered_attempts_by_type": {t: sum(1 for r in rows if r["unrecovered_failure"] == t)
                                         for t in {r["unrecovered_failure"] for r in rows if r["unrecovered_failure"]}},
        "verifier_pass_rate": round(sum(r["verifier_passed"] for r in rows) / n, 3),
    }
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part2_reliability.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    with (RAW / "part2_reliability.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    stamp(f"summary {json.dumps(summary)}")


def compare(n: int) -> None:
    stamp(f"Part 3 compare - original loop vs Reflexion, each task x{n} - settings {SETTINGS}")
    store = ReflectionStore()
    orig, refl = [], []
    for rep in range(n):
        for case in CASES["cases"]:
            stamp(f"[original] case {case['id']} rep {rep + 1}")
            r = run_agent(case["prompt"], required_tools=case["required_tools"], log=lambda _m: None)
            check = verify(case, r)
            orig.append({"case": case["id"], "rep": rep + 1, "success": check["passed"], "problems": check["problems"],
                         "unsupported_claims": len(unsupported_claims(r)), "retries": 0, "tool_calls": r["tool_calls"],
                         "tokens": r["tokens"], "latency_ms": r["latency_ms"], "final": r["final"]})
            stamp(f"[reflexion] case {case['id']} rep {rep + 1}")
            x = run_reflexion(case, store=store, log=lambda m: print(m, flush=True))
            refl.append({**{k: x[k] for k in ("case", "run_id", "stop_reason", "success", "retries", "tool_calls",
                                                "tokens", "latency_ms", "unsupported_claims")}, "rep": rep + 1,
                         "attempts": x["attempts"]})
            stamp(f"  original={'PASS' if check['passed'] else 'FAIL'}  reflexion={x['stop_reason']} retries={x['retries']}")

    def agg(rows, retry_key="retries"):
        return {"runs": len(rows), "task_success": round(sum(r["success"] for r in rows) / len(rows), 3),
                "unsupported_claims": sum(r["unsupported_claims"] for r in rows),
                "retry_rate": round(sum(1 for r in rows if r[retry_key] > 0) / len(rows), 3),
                "tool_calls_mean": round(statistics.mean(r["tool_calls"] for r in rows), 2),
                "tokens_mean": round(statistics.mean(r["tokens"] for r in rows)),
                "latency_ms_mean": round(statistics.mean(r["latency_ms"] for r in rows))}

    summary = {"settings": SETTINGS, "repeats": n, "original": agg(orig), "reflexion": agg(refl),
               "reflexion_stop_reasons": {s: sum(1 for r in refl if r["stop_reason"] == s)
                                          for s in ("success", "budget_exhausted", "human_review")}}
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part3_comparison.json").write_text(json.dumps({"summary": summary, "original": orig, "reflexion": refl},
                                                          indent=2), encoding="utf-8")
    stamp(f"summary {json.dumps(summary)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
    mode = sys.argv[1]
    if mode == "demo":
        demo()
    elif mode == "reliability":
        reliability(int(sys.argv[2]) if len(sys.argv) > 2 else 21)
    elif mode == "compare":
        compare(int(sys.argv[2]) if len(sys.argv) > 2 else 3)
