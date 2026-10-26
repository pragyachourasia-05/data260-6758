"""Assemble reports/hw07/RUN_LOG.txt from the real console outputs saved in reports/hw07/raw/.

    python backend/make_hw07_runlog.py
"""
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "reports" / "hw07" / "raw"
SECTIONS = [
    ("Part 1 - users table migration", "part1_migration_console.txt"),
    ("Part 2 - demo tasks A, B, C and the nonexistent-id case", "part2_demo_console.txt"),
    ("Part 2 - 21-attempt reliability run", "part2_reliability_console.txt"),
    ("Part 3 - original loop vs Reflexion", "part3_compare_console.txt"),
    ("Part 4 - building the two scenario CSVs from public Bay Wheels data", "part4_build_scenarios_console.txt"),
    ("Part 4 - both scenarios through POST /bikeshare/run", "part4_runs_console.txt"),
    ("Part 5 - building the hostile fixtures", "part5_build_console.txt"),
    ("Part 5 - 3 attacks x 3 conditions", "part5_attacks_console.txt"),
    ("Part 6 - file tools + safety gate", "part6_file_tools_console.txt"),
    ("Verification (verify_hw07.py)", "verify_console.txt"),
]


def main() -> None:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out = ["DATA-260 HW7 RUN_LOG - Pragya Chourasia (SID4 6758)",
           f"assembled {datetime.now().isoformat(timespec='seconds')} at commit {commit or 'unknown'}",
           "machine: Intel Core i5-1335U, 16 GB RAM, Windows 11; llama3.2:3b and qwen3:8b via Ollama; MySQL + MongoDB in Docker",
           "Each section is the unedited console output of the run, with its own timestamps."]
    for title, name in SECTIONS:
        p = RAW / name
        out += ["", "=" * 100, f"## {title}", f"## source: reports/hw07/raw/{name}", "=" * 100,
                p.read_text(encoding="utf-8", errors="replace").rstrip() if p.exists() else "(missing)"]
    (ROOT / "reports" / "hw07" / "RUN_LOG.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("RUN_LOG.txt written")


if __name__ == "__main__":
    main()
