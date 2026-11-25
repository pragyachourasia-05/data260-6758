"""Print my saved HW11 self-check results.

    python code/hw11_show.py
"""
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    v = json.loads((ROOT / "reports" / "hw11" / "verification.json").read_text(encoding="utf-8"))
    print(f"{v['homework']}  SID4 {v['sid4']}  commit {v['commit_hash']}  seed {v['seed']}  verify_seed {v['verify_seed']}\n")
    for c in v["checks"]:
        print(f"{'PASS' if c['passed'] else 'FAIL'}  {c['name']}")
        print(textwrap.fill(c["detail"], 100, initial_indent="      ", subsequent_indent="      "))
    print(f"\nOverall: {'PASS' if v['passed'] else 'FAIL'}")
