"""Assemble reports/hw06/RUN_LOG.txt from the real console outputs saved in reports/hw06/raw/.

    python backend/make_hw06_runlog.py
"""
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "reports" / "hw06" / "raw"

SECTIONS = [
    ("Part 1 - MongoDB CRUD + validation (curl)", RAW / "part1_crud_console.txt"),
    ("Part 2 - 12-message memory session (backend/run_hw06_chat_demo.py)", RAW / "part2_demo_console.txt"),
    ("Part 3 - memory cost sweep (backend/run_hw06_memory_cost.py; run2 + run3 reruns of n4/n12)", RAW / "part3_console.txt"),
    ("Part 4 - /compact session (code/hw1_client.py < cases/part4_session_a.txt)", RAW / "part4_compact_session.txt"),
    ("Part 4 - /dream session before the key-reuse fix", RAW / "part4_dream_session_before_fix.txt"),
    ("Part 4 - /dream + /compact session after the fix", RAW / "part4_dream_session.txt"),
    ("Part 4 - AGENT.md check of the generated function (before correction)", RAW / "agent_md_generated_v1" / "agent_md_check.json"),
    ("Part 4 - offline tests + AGENT.md check (after correction)", RAW / "part4_tests_console.txt"),
    ("Verification (verify_hw06.py)", RAW / "verify_console.txt"),
]


def main() -> None:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = [
        "DATA-260 HW6 RUN_LOG - Pragya Chourasia (SID4 6758)",
        f"assembled {datetime.now().isoformat(timespec='seconds')} at commit {commit or 'unknown'}",
        "machine: Intel Core i5-1335U, 16 GB RAM, Windows 11; model llama3.2:3b via Ollama; MongoDB 7.0 in Docker",
        "Each section below is the unedited console output of the run; timestamps are inside each section.",
    ]
    for title, path in SECTIONS:
        out += ["", "=" * 100, f"## {title}", f"## source: {path.relative_to(ROOT)}", "=" * 100]
        out.append(path.read_text(encoding="utf-8").rstrip() if path.exists() else "(missing)")
    (ROOT / "reports" / "hw06" / "RUN_LOG.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"RUN_LOG.txt written ({sum(1 for _ in out)} lines)")


if __name__ == "__main__":
    main()
