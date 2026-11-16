"""HW10 self-check; run from the repository root (Redis up; no model needed).

    python verify_hw10.py        (or: make verify-hw10)

Checks the saved evidence and two live behaviours (the judge timeout and the dashboard pages), then writes
reports/hw10/verification.json. Application code is not modified.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports" / "hw10"
RAW = REPORTS / "raw"
SID4 = 6758
VERIFY_SEED = 260000 + SID4
SPAN_FIELDS = {"trace_id", "stage", "start", "end", "status", "error"}
MISS_PATH = ["cache_lookup", "queue:s6758_inbox", "planner", "queue:s6758_tasks", "writer", "queue:s6758_drafts",
             "reviewer", "queue:s6758_final", "evaluation"]


def check(name, fn):
    try:
        return {"name": name, "passed": True, "detail": fn() or "ok"}
    except Exception as exc:  # each check reports its own failure
        return {"name": name, "passed": False, "detail": f"{type(exc).__name__}: {exc}"}


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def spans_by_trace() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for line in (RAW / "spans.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            s = json.loads(line)
        except json.JSONDecodeError:
            continue  # known: 4 lines cut by concurrent appends before the file lock was added
        expect(SPAN_FIELDS <= set(s), f"span missing fields: {s}")
        out.setdefault(s["trace_id"], []).append(s)
    return out


def examples() -> dict[str, dict]:
    return {e["label"]: e for e in load(RAW / "trace_examples.json")}


def trace_check():
    spans, ex = spans_by_trace(), examples()
    miss = {s["stage"]: s for s in spans[ex["cache_miss"]["trace_id"]]}
    expect(all(st in miss for st in MISS_PATH), f"miss trace lacks {[st for st in MISS_PATH if st not in miss]}")
    expect(miss["cache_lookup"]["cache"] == "miss" and all(miss[st]["status"] == "ok" for st in MISS_PATH), "miss trace not clean")
    hit = spans[ex["cache_hit"]["trace_id"]]
    expect([s["cache"] for s in hit if s["stage"] == "cache_lookup"] == ["hit"], "hit trace has no cache hit")
    expect(not any(s["stage"] in ("planner", "writer", "reviewer") for s in hit), "hit trace reached the agents")
    failed = [s for s in spans[ex["failed"]["trace_id"]] if s["status"] == "error"]
    expect(failed and failed[0]["error"], "failed trace has no error span")
    return f"miss: {len(MISS_PATH)} stages on one trace_id; hit: cache only; failed at {failed[0]['stage']}"


def evaluation_check():
    ex = examples()
    recs = [json.loads(x) for x in (RAW / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()]
    rec = next(r for r in recs if r["trace_id"] == ex["cache_miss"]["trace_id"])
    scores = [rec["plan_quality"]["score"], rec["writer_helpfulness"]["score"], rec["final_answer_helpfulness"]["score"]]
    expect(all(isinstance(s, int) and 1 <= s <= 5 for s in scores), f"scores {scores}")
    expect(rec["plan_quality"]["reason"] and rec["final_answer_helpfulness"]["final_answer"], "reason or final answer missing")
    fvd = rec["final_vs_draft"]
    expect(fvd["difference"] == fvd["final_score"] - fvd["draft_score"] and fvd["interpretation"], "final-vs-draft incomplete")
    expect(all(rec["messages"][r]["offset"] is not None for r in ("plan", "draft", "final")), "raw messages missing")
    return f"{len(recs)} evaluation(s); example scores plan/draft/final = {scores}"


def frozen_check():
    cases = load(ROOT / "evaluation" / "eval_cases.json")
    with (ROOT / "evaluation" / "human_labels.csv").open(encoding="utf-8") as f:
        labels = list(csv.DictReader(f))
    expect(len(cases) == 20 and len(labels) == 20, "need 20 cases and 20 labels")
    expect(all(r["helpfulness"] in {"1", "2", "3", "4", "5"} for r in labels), "labels must be 1-5")
    when = subprocess.run(["git", "log", "--reverse", "--format=%ct", "--", "evaluation/human_labels.csv"], cwd=ROOT,
                          capture_output=True, text=True).stdout.split()
    expect(when, "human_labels.csv is not committed")
    first_run = int((RAW / "judge_runs.json").stat().st_ctime)  # on Windows st_ctime is when the file was created
    expect(int(when[0]) < first_run, "labels were committed after the judge ran")
    return f"20 cases and labels committed {datetime.fromtimestamp(int(when[0]), timezone.utc):%Y-%m-%d %H:%M} UTC, before the judge runs"


def validation_check():
    v = load(RAW / "judge_validation.json")
    runs = load(RAW / "judge_runs.json")
    expect(len(runs) == 3 and all(len(r) == 20 for r in runs.values()), "need 3 runs x 20 cases")
    for k in ("spearman_rho", "mean_abs_diff"):
        expect(k in v["agreement_by_run"]["run1"], f"{k} missing")
    expect({"pct_cases_changed", "mean_abs_change", "max_abs_change"} <= set(v["repeatability"]), "repeatability missing")
    return (f"rho {v['agreement_by_run']['run1']['spearman_rho']}, MAD {v['agreement_by_run']['run1']['mean_abs_diff']}, "
            f"{v['repeatability']['cases_where_score_changed']}/20 cases changed across runs")


def latency_check():
    s = load(RAW / "latency_summary.json")
    expect(s["confirmed_misses"] == 50 and s["served_from_cache"] == 0, f"misses {s['confirmed_misses']}, hits {s['served_from_cache']}")
    expect([t["stage"] for t in s["table"]] == ["Cache lookup", "Planner", "Writer", "Reviewer", "Queue wait (total)", "Evaluation"], "stage rows")
    return f"50 confirmed misses; e2e p50 {s['e2e_p50_ms'] / 1000:.1f}s, p95 {s['e2e_p95_ms'] / 1000:.1f}s"


def judge_timeout_check():
    from deepeval.models import OllamaModel

    from evaluation.judge import HELPFULNESS_STEPS, metric, score

    dead = metric("Helpfulness", HELPFULNESS_STEPS, OllamaModel(model="llama3.2:3b", base_url="http://127.0.0.1:9", temperature=0))
    t = time.time()
    r = score(dead, f"verify {VERIFY_SEED}", "answer", timeout=30)
    took = time.time() - t
    expect(r["score"] is None and r["error"] and took < 35, f"unavailable judge: {r} after {took:.1f}s")
    return f"unavailable judge returns an error in {took:.1f}s instead of hanging"


def dashboard_check():
    from streamlit.testing.v1 import AppTest

    for page in ("Summary", "Evaluation", "Trace lookup"):
        at = AppTest.from_file(str(ROOT / "dashboard" / "app.py"), default_timeout=60).run()
        at.sidebar.radio[0].set_value(page).run()
        expect(not at.exception, f"{page}: {at.exception}")
    return "Summary, Evaluation and Trace lookup pages render without errors"


def key_prefix_check():
    import redis

    client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    bad = [k for k in client.scan_iter("*", count=500) if not k.startswith("s6758")]
    expect(not bad, f"keys without the prefix: {bad[:5]}")
    return "every Redis key starts with s6758"


def main() -> int:
    checks = [check("trace_examples_hit_miss_failed", trace_check),
              check("evaluator_four_criteria", evaluation_check),
              check("eval_cases_and_labels_frozen", frozen_check),
              check("judge_validation_saved", validation_check),
              check("latency_50_confirmed_misses", latency_check),
              check("judge_timeout_bounded", judge_timeout_check),
              check("dashboard_pages_render", dashboard_check),
              check("redis_keys_prefixed", key_prefix_check)]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = {"homework": "HW10", "sid4": str(SID4), "commit_hash": commit,
              "model_configuration": {"agents": "llama3.2:3b via Ollama, temperature 0, seed 6758",
                                      "judge": "DeepEval GEval with OllamaModel llama3.2:3b, temperature 0, seed 6758, rubric 1-5",
                                      "cache": "Redis vector index, all-MiniLM-L6-v2, cosine, threshold 0.95",
                                      "this_check": "no LLM call (the judge check points at a closed port)"},
              "seed": SID4, "verify_seed": VERIFY_SEED, "checks": checks, "passed": all(c["passed"] for c in checks)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
