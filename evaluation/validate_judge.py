"""HW10 Part 3: compare the judge with my human labels, then test repeatability.

    python evaluation/validate_judge.py run      3 judge runs over the 20 frozen drafts (resumable)
    python evaluation/validate_judge.py stats    Spearman, mean absolute difference, repeatability

It refuses to run until human_labels.csv is complete and committed unchanged, so the labels are fixed before
any judge score exists.
"""
import csv
import itertools
import json
import subprocess
import sys
from pathlib import Path

from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from evaluation.judge import HELPFULNESS_STEPS, JUDGE_MODEL, JUDGE_SEED, metric, score  # noqa: E402

RAW = ROOT / "reports" / "hw10" / "raw"
RUNS = RAW / "judge_runs.json"
PER_CASE = RAW / "judge_vs_human.csv"
SUMMARY = RAW / "judge_validation.json"
N_RUNS = 3


def labels() -> dict[str, int]:
    with (HERE / "human_labels.csv").open(encoding="utf-8") as f:
        rows = {r["case_id"]: r["helpfulness"].strip() for r in csv.DictReader(f)}
    bad = [k for k, v in rows.items() if v not in {"1", "2", "3", "4", "5"}]
    if bad:
        sys.exit(f"human_labels.csv is not complete (1-5 needed): {bad}")
    return {k: int(v) for k, v in rows.items()}


def frozen() -> None:
    files = ["evaluation/eval_cases.json", "evaluation/human_labels.csv"]
    for f in files:
        tracked = subprocess.run(["git", "log", "--oneline", "-1", "--", f], cwd=ROOT, capture_output=True, text=True).stdout
        dirty = subprocess.run(["git", "status", "--porcelain", "--", f], cwd=ROOT, capture_output=True, text=True).stdout
        if not tracked.strip() or dirty.strip():
            sys.exit(f"{f} must be committed (and unchanged) before the judge runs")


def run():
    frozen()
    labels()
    cases = json.loads((HERE / "eval_cases.json").read_text(encoding="utf-8"))
    runs = json.loads(RUNS.read_text(encoding="utf-8")) if RUNS.exists() else {}
    m = metric("Helpfulness", HELPFULNESS_STEPS)
    for r in range(1, N_RUNS + 1):
        done = runs.setdefault(str(r), {})
        for c in cases:
            if c["case_id"] in done:
                continue
            done[c["case_id"]] = score(m, c["question"], c["draft"], c["listing_facts"])
            RAW.mkdir(parents=True, exist_ok=True)
            RUNS.write_text(json.dumps(runs, indent=2), encoding="utf-8")
            print(f"run {r} {c['case_id']} score={done[c['case_id']]['score']} error={done[c['case_id']]['error']}", flush=True)
    stats()


def stats():
    human = labels()
    runs = json.loads(RUNS.read_text(encoding="utf-8"))
    ids = sorted(human)
    table = []
    for cid in ids:
        scores = [runs[str(r)][cid]["score"] for r in range(1, N_RUNS + 1)]
        table.append({"case_id": cid, "human": human[cid], **{f"run{r}": s for r, s in zip(range(1, N_RUNS + 1), scores, strict=True)}})
    with PER_CASE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)

    per_run = {}
    for r in range(1, N_RUNS + 1):
        pairs = [(t["human"], t[f"run{r}"]) for t in table if t[f"run{r}"] is not None]
        h, j = zip(*pairs, strict=True)
        rho, p = spearmanr(h, j)
        per_run[f"run{r}"] = {"n": len(pairs), "spearman_rho": round(float(rho), 3), "p_value": round(float(p), 4),
                              "mean_abs_diff": round(sum(abs(a - b) for a, b in pairs) / len(pairs), 3)}
    complete = [t for t in table if all(t[f"run{r}"] is not None for r in range(1, N_RUNS + 1))]
    changed = [t["case_id"] for t in complete if len({t[f"run{r}"] for r in range(1, N_RUNS + 1)}) > 1]
    deltas = [abs(t[f"run{a}"] - t[f"run{b}"]) for t in complete for a, b in itertools.combinations(range(1, N_RUNS + 1), 2)]
    spread = [max(t[f"run{r}"] for r in range(1, N_RUNS + 1)) - min(t[f"run{r}"] for r in range(1, N_RUNS + 1)) for t in complete]
    summary = {
        "judge": {"model": JUDGE_MODEL, "temperature": 0, "seed": JUDGE_SEED, "metric": "GEval Helpfulness, rubric 1-5",
                  "runs": N_RUNS, "inputs": "evaluation/eval_cases.json (20 drafts)"},
        "agreement_by_run": per_run,
        "repeatability": {"cases_compared": len(complete), "cases_where_score_changed": len(changed),
                          "pct_cases_changed": round(100 * len(changed) / len(complete), 1), "changed_cases": changed,
                          "pairwise_comparisons": len(deltas), "pct_pairs_changed": round(100 * sum(d > 0 for d in deltas) / len(deltas), 1),
                          "mean_abs_change": round(sum(deltas) / len(deltas), 3), "max_abs_change": max(deltas),
                          "max_spread_per_case": max(spread)},
        "judge_errors": sum(1 for r in runs.values() for v in r.values() if v["error"]),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{'case':6}{'human':>7}" + "".join(f"{'run' + str(r):>7}" for r in range(1, N_RUNS + 1)))
    for t in table:
        print(f"{t['case_id']:6}{t['human']:>7}" + "".join(f"{str(t[f'run{r}']):>7}" for r in range(1, N_RUNS + 1)))
    print(json.dumps({k: summary[k] for k in ("agreement_by_run", "repeatability")}, indent=2))


if __name__ == "__main__":
    {"run": run, "stats": stats}[sys.argv[1]]()
