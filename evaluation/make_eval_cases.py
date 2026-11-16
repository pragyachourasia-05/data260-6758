"""HW10 Part 3.1: freeze 20 Writer drafts into eval_cases.json and write a blank human_labels.csv.

    python evaluation/make_eval_cases.py

The drafts come from my HW9 Part 3 agent run (raw/part3_agent_memo.json): every question there went through
Planner -> Writer -> Reviewer once, and the Reviewer passes the Writer's draft through unchanged. I take every
second question (0, 2, 4, ... 38) so the set is fixed by a rule, not picked by hand.
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))
MEMO = ROOT / "reports" / "hw09" / "raw" / "part3_agent_memo.json"


def main():
    # the same listing facts the agents were given in HW9 (read from s6758_rel)
    from app.semantic_cache import find_listing, listing_context

    memo = json.loads(MEMO.read_text(encoding="utf-8"))
    cases = []
    for n, (question, run) in enumerate(list(memo.items())[::2], 1):
        cases.append({"case_id": f"ec{n:02d}", "question": question, "listing_facts": listing_context(find_listing(question)),
                      "draft": run["answer"], "reviewer_status": run["status"], "agent_ms": run["agent_ms"],
                      "source": "reports/hw09/raw/part3_agent_memo.json"})
    (HERE / "eval_cases.json").write_text(json.dumps(cases, indent=2), encoding="utf-8")
    labels = HERE / "human_labels.csv"
    if not labels.exists():  # never overwrite labels once they exist
        with labels.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["case_id", "helpfulness"])
            w.writerows([[c["case_id"], ""] for c in cases])
    print(f"{len(cases)} cases written")


if __name__ == "__main__":
    main()
