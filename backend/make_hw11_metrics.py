"""Builds reports/hw11/METRICS.md and RUN_LOG.txt from my saved Muse results.

    python backend/make_hw11_metrics.py
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports" / "hw11"


def main():
    r = json.loads((REPORTS / "raw" / "muse_results.json").read_text(encoding="utf-8"))
    gold = json.loads((ROOT / "stock-watch" / "golden" / "gold_pragya.json").read_text(encoding="utf-8"))
    m = r["metrics"]
    md = ["# HW11 Metrics (Meta Muse, free tier)", "", "| Metric | Value |", "| --- | --- |"]
    md += [f"| {k} | {v} |" for k, v in m.items() if k != "note"]
    md += ["", m["note"], "", "## Golden set", "", "| Case | Category | Expected | Muse |", "| --- | --- | --- | --- |"]
    md += [f"| {c['case_id']} | {c['category']} | {c['expected']} | {r['per_case'][c['case_id']]} |" for c in gold["cases"]]
    live = r["live_runs"][1]
    md += ["", "## Live run", "", f"{live['run_id']}: {live['summary']}; latency {live['latency_seconds']} s.",
           f"HIGH alert {live['alert']['title']} (effect {live['alert']['effect_id']}, score {live['alert']['score']}).", "",
           f"Usage: {r['usage']['shown_as']}.", ""]
    (REPORTS / "METRICS.md").write_text("\n".join(md), encoding="utf-8")
    log = [f"DATA-260 HW11 RUN_LOG - Pragya Chourasia - SID4 6758 - built {datetime.now():%Y-%m-%d %H:%M:%S}\n\n",
           "== Muse results (copied from my Muse chats)\n", json.dumps(r, indent=2), "\n\n== Live NVDA alert trace\n",
           (REPORTS / "raw" / "muse_live_trace.json").read_text(encoding="utf-8"), "\n"]
    ver = REPORTS / "verification.json"
    if ver.exists():
        log += ["\n== verify_hw11.py\n", ver.read_text(encoding="utf-8"), "\n"]
    (REPORTS / "RUN_LOG.txt").write_text("".join(log), encoding="utf-8")
    print("METRICS.md and RUN_LOG.txt written")


if __name__ == "__main__":
    main()
