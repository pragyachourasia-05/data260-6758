"""Print saved HW10 results in the terminal.

    python code/hw10_show.py trace cache_miss | cache_hit | failed
    python code/hw10_show.py eval            evaluator record for the cache-miss example
    python code/hw10_show.py evalsummary     scores over every evaluated request
    python code/hw10_show.py judge           Part 3 per-case table and statistics
    python code/hw10_show.py verify
"""
import csv
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "reports" / "hw10" / "raw"
WIDTH = 105


def load(name):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


def jsonl(name):
    out = []
    for x in (RAW / name).read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(x))
        except json.JSONDecodeError:
            continue  # 4 span lines were cut by two processes writing at once (before the file lock)
    return out


def wrap(label, text):
    print(textwrap.fill(" ".join(str(text).split()), WIDTH, initial_indent=label, subsequent_indent=" " * len(label)))


def example(label):
    return next(e for e in load("trace_examples.json") if e["label"] == label)


def trace(label):
    ex = example(label)
    spans = sorted((s for s in jsonl("spans.jsonl") if s["trace_id"] == ex["trace_id"]), key=lambda s: s["start_ts"])
    print(f"{label}  trace_id={ex['trace_id']}")
    wrap("question: ", ex["question"])
    print(f"\n{'stage':34}{'start (UTC)':26}{'end (UTC)':26}{'ms':>10}  status")
    for s in spans:
        extra = f"  cache={s['cache']} sim={s.get('similarity')}" if s["stage"] == "cache_lookup" else ""
        print(f"{s['stage']:34}{s['start']:26}{s['end']:26}{s['duration_ms']:>10.1f}  {s['status']}{extra}")
        if s["error"]:
            wrap("    error: ", s["error"])


def eval_():
    ex = example("cache_miss")
    r = next(x for x in jsonl("evaluations.jsonl") if x["trace_id"] == ex["trace_id"])
    print(f"trace_id={r['trace_id']}  judge={r['judge']}")
    wrap("question: ", r["question"])
    m = r["messages"]
    print("joined on correlation_id: " + ", ".join(f"{k}={v['topic']}@{v['partition']}/{v['offset']}" for k, v in m.items()))
    print()
    wrap("Plan: ", " | ".join(r["plan_quality"]["plan"]))
    wrap(f"Plan Quality = {r['plan_quality']['score']}: ", r["plan_quality"]["reason"])
    wrap(f"Writer Helpfulness = {r['writer_helpfulness']['score']}: ", r["writer_helpfulness"]["reason"])
    wrap(f"Final Answer Helpfulness = {r['final_answer_helpfulness']['score']}: ", r["final_answer_helpfulness"]["reason"])
    wrap("Final answer: ", r["final_answer_helpfulness"]["final_answer"])
    f = r["final_vs_draft"]
    print(f"\nFinal-vs-Draft: draft={f['draft_score']} final={f['final_score']} difference={f['difference']} same_text={f['same_text']}")
    wrap("Interpretation: ", f["interpretation"])


def evalsummary():
    rows = [x for x in jsonl("evaluations.jsonl") if not x["errors"]]
    print(f"{len(rows)} evaluated requests (judge llama3.2:3b, scale 1-5)\n")
    print(f"{'criterion':28}{'mean':>6}   1   2   3   4   5")
    for k, name in (("plan_quality", "Plan Quality"), ("writer_helpfulness", "Writer Helpfulness"),
                    ("final_answer_helpfulness", "Final Answer Helpfulness")):
        v = [x[k]["score"] for x in rows]
        print(f"{name:28}{sum(v) / len(v):>6.2f}" + "".join(f"{v.count(s):>4}" for s in range(1, 6)))
    d = [x["final_vs_draft"]["difference"] for x in rows]
    same = sum(x["final_vs_draft"]["same_text"] for x in rows)
    print(f"\nFinal text identical to draft: {same}/{len(rows)}")
    print("Final - draft score: " + ", ".join(f"{k:+d} x{d.count(k)}" for k in sorted(set(d))))
    print("Reviewer: " + ", ".join(f"{s} {sum(x['final_answer_helpfulness']['reviewer_status'] == s for x in rows)}" for s in ("approved", "rejected")))


def judge():
    with (RAW / "judge_vs_human.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"{'case':6}{'human':>7}{'run1':>6}{'run2':>6}{'run3':>6}")
    for r in rows:
        print(f"{r['case_id']:6}{r['human']:>7}{r['run1']:>6}{r['run2']:>6}{r['run3']:>6}")
    v = load("judge_validation.json")
    print()
    for k, a in v["agreement_by_run"].items():
        print(f"{k}: Spearman rho = {a['spearman_rho']:.3f} (p = {a['p_value']}), mean absolute difference = {a['mean_abs_diff']:.2f}")
    r = v["repeatability"]
    print(f"repeatability: score changed in {r['cases_where_score_changed']}/{r['cases_compared']} cases ({r['pct_cases_changed']}%), "
          f"{r['pct_pairs_changed']}% of run pairs; mean abs change {r['mean_abs_change']}, max {r['max_abs_change']}")


def verify():
    v = json.loads((ROOT / "reports" / "hw10" / "verification.json").read_text(encoding="utf-8"))
    print(f"{v['homework']}  SID4 {v['sid4']}  commit {v['commit_hash']}  seed {v['seed']}  verify_seed {v['verify_seed']}\n")
    for c in v["checks"]:
        print(f"{'PASS' if c['passed'] else 'FAIL'}  {c['name']}")
        wrap("      ", c["detail"])
    print(f"\nOverall: {'PASS' if v['passed'] else 'FAIL'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    if mode == "trace":
        trace(sys.argv[2])
    else:
        {"eval": eval_, "evalsummary": evalsummary, "judge": judge, "verify": verify}[mode]()
