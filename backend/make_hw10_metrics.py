"""Builds reports/hw10/METRICS.md and RUN_LOG.txt from the saved HW10 results.

    python backend/make_hw10_metrics.py
"""
import csv
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports" / "hw10"
RAW = REPORTS / "raw"


def jsonl(name):
    out = []
    for line in (RAW / name).read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 4 span lines were cut by concurrent appends before the file lock
    return out


def load(name):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


def metrics():
    evals = [e for e in jsonl("evaluations.jsonl") if not e["errors"]]
    lat, val = load("latency_summary.json"), load("judge_validation.json")
    mean = lambda k: sum(e[k]["score"] for e in evals) / len(evals)  # noqa: E731
    md = ["# HW10 Metrics", "", "## Part 2 - Evaluator (judge llama3.2:3b, GEval, scale 1-5)", "",
          "| Criterion | Mean | n |", "| --- | --- | --- |",
          f"| Plan Quality | {mean('plan_quality'):.2f} | {len(evals)} |",
          f"| Writer Helpfulness | {mean('writer_helpfulness'):.2f} | {len(evals)} |",
          f"| Final Answer Helpfulness | {mean('final_answer_helpfulness'):.2f} | {len(evals)} |", "",
          f"Final answer identical to the draft in {sum(e['final_vs_draft']['same_text'] for e in evals)} of {len(evals)} requests.", "",
          "## Part 3 - Judge vs my labels (20 drafts, 3 runs)", "", "| Run | Spearman rho | p | Mean abs difference |", "| --- | --- | --- | --- |"]
    md += [f"| {k} | {a['spearman_rho']} | {a['p_value']} | {a['mean_abs_diff']} |" for k, a in val["agreement_by_run"].items()]
    r = val["repeatability"]
    md += ["", f"Repeatability: score changed in {r['cases_where_score_changed']}/{r['cases_compared']} cases; "
           f"mean abs change {r['mean_abs_change']}, max {r['max_abs_change']}.", "",
           "## Part 4 - 50 confirmed cache misses", "", "| Stage | p50 (ms) | p95 (ms) | % of cache-miss end-to-end |", "| --- | --- | --- | --- |"]
    md += [f"| {t['stage']} | {t['p50_ms']} | {t['p95_ms']} | {t['pct_of_e2e']}% |" for t in lat["table"]]
    md += [f"| End-to-end | {lat['e2e_p50_ms']} | {lat['e2e_p95_ms']} | |", "", f"End-to-end = {lat['e2e_definition']}.", "",
           "Trace examples: " + ", ".join(f"{e['label']} = {e['trace_id']}" for e in load("trace_examples.json")), ""]
    (REPORTS / "METRICS.md").write_text("\n".join(md), encoding="utf-8")


def runlog():
    out = [f"DATA-260 HW10 RUN_LOG - Pragya Chourasia - SID4 6758 - built {datetime.now():%Y-%m-%d %H:%M:%S}\n"]
    ps = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}"], capture_output=True, text=True).stdout
    out += ["\n== docker ps\n", ps, "\n== trace examples (spans in stage order)\n"]
    spans = jsonl("spans.jsonl")
    for e in load("trace_examples.json"):
        out.append(f"\n{e['label']} trace_id={e['trace_id']} question={e['question']!r}\n")
        for s in sorted((s for s in spans if s["trace_id"] == e["trace_id"]), key=lambda s: s["start_ts"]):
            out.append(f"  {s['stage']:32} {s['start']} -> {s['end']} {s['duration_ms']:>10} ms {s['status']} {s['error'] or ''}\n")
    out.append("\n== latency run (50 requests)\n")
    out += [json.dumps(r) + "\n" for r in load("latency_run.json")]
    out += ["\n== latency summary\n", json.dumps(load("latency_summary.json"), indent=2) + "\n", "\n== judge vs human (per case)\n"]
    with (RAW / "judge_vs_human.csv").open(encoding="utf-8") as f:
        out += [",".join(row) + "\n" for row in csv.reader(f)]
    out += ["\n== judge validation\n", json.dumps(load("judge_validation.json"), indent=2) + "\n", "\n== evaluator records (scores)\n"]
    for e in jsonl("evaluations.jsonl"):
        out.append(f"{e['trace_id']} plan={e['plan_quality']['score']} draft={e['writer_helpfulness']['score']} "
                   f"final={e['final_answer_helpfulness']['score']} same_text={e['final_vs_draft']['same_text']} errors={e['errors']}\n")
    (REPORTS / "RUN_LOG.txt").write_text("".join(out), encoding="utf-8")


if __name__ == "__main__":
    metrics()
    runlog()
    print("METRICS.md and RUN_LOG.txt written")
