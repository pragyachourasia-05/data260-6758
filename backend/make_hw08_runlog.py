"""Builds reports/hw08/RUN_LOG.txt from the saved run logs.

    python backend/make_hw08_runlog.py
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports" / "hw08"
RAW = REPORTS / "raw"


def section(title):
    return f"\n{'=' * 100}\n{title}\n{'=' * 100}\n"


def main():
    out = [f"DATA-260 HW8 RUN_LOG - Pragya Chourasia - SID4 6758 - built {datetime.now():%Y-%m-%d %H:%M:%S}\n"]
    ps = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}"],
                        capture_output=True, text=True).stdout
    out += [section("Part 1 - docker ps"), ps]

    demo = json.loads((RAW / "part1_demo.json").read_text(encoding="utf-8"))
    out += [section("Part 1 - homework_demo.py results (raw/part1_demo.json)"),
            json.dumps({k: demo[k] for k in ("create", "get", "checks")}, indent=2) + "\n",
            "Error cases:\n"]
    out += [f"  {e['operation']:15s} sent correlation_id={e['sent_correlation_id']} -> {json.dumps(e['response'])}\n"
            for e in demo["errors"]]
    out += [section("Part 1 - CREATE_LISTING -> GET_LISTING full sequence (raw/part1_sequence.log)"),
            (RAW / "part1_sequence.log").read_text(encoding="utf-8")]

    out.append(section("Part 2 - one message journey s6758_inbox -> s6758_final (raw/part2_journey.jsonl)"))
    final = None
    for line in (RAW / "part2_journey.jsonl").read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        extra = {k: v for k, v in e.items() if k not in ("ts", "agent", "event")}
        out.append(f"{e['ts']} [{e['agent']}] {e['event']} {json.dumps(extra)}\n")
        if e["agent"] == "SENDER" and e["event"].startswith("received result"):
            final = e
    out.append(f"\nfinal status: {final.get('status') if final else 'missing'}\n")

    excerpts = RAW / "part3_log_excerpts.txt"
    if excerpts.exists():
        out += [section("Part 3 - failure tests (full logs in raw/part3/)"), excerpts.read_text(encoding="utf-8")]

    (REPORTS / "RUN_LOG.txt").write_text("".join(out), encoding="utf-8")
    print(f"wrote {REPORTS / 'RUN_LOG.txt'}")


if __name__ == "__main__":
    main()
