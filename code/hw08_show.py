"""Print saved HW8 Part 3 logs in the terminal.

    python code/hw08_show.py duplicate
    python code/hw08_show.py consumer_death
    python code/hw08_show.py poison
    python code/hw08_show.py ordering
"""
import json
import re
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "reports" / "hw08" / "raw"
LOGS = RAW / "part3"
RESULTS = json.loads((RAW / "part3_results.json").read_text(encoding="utf-8"))


def lines(name, *keep):
    for ln in (LOGS / f"{name}.log").read_text(encoding="utf-8").splitlines():
        if ln[:4].isdigit() and any(k in ln for k in keep):
            ln = re.sub(r"^2026-\d\d-\d\dT", "", ln)
            print(re.sub(r' (steps|idempotency)=.*$', "", ln))


def duplicate():
    for mode in ("before", "after"):
        r = RESULTS["duplicate"][mode]
        print(f"--- Duplicate delivery, {mode} fix (Planner log) ---")
        lines(f"duplicate_{mode}_planner", "received", "sent to", "duplicate")
        print(f"messages in s6758_final={r['messages_in_final']}  agent runs={r['agent_runs']}\n")


def consumer_death():
    for mode in ("before", "after"):
        r = RESULTS["consumer_death"][mode]
        print(f"--- Writer killed mid-work, {mode} fix (Writer log, both runs) ---")
        lines(f"consumer_death_{mode}_writer", "listening", "received", "sent to", "offset committed")
        print(f"committed offset when killed={r['committed_offset_when_killed']}  "
              f"redelivered={r['redelivered_after_restart']}  drafts={r['drafts_in_topic']}  "
              f"committed offset at end={r['committed_offset_at_end']}\n")


def poison():
    for mode in ("before", "after"):
        r = RESULTS["poison"][mode]
        print(f"--- Poison message, {mode} fix (Writer log) ---")
        lines(f"poison_{mode}_writer", "received", "failed", "moved to", "sent to")
        print(f"crashes={r['crashes']}  dead-letter messages={r['dead_letter_messages']}  "
              f"later message processed={r['good_message_processed']}\n")
    print("Message in s6758_dead_letter:", json.dumps(RESULTS["poison"]["after"]["dead_letter_sample"]))


def ordering():
    for mode in ("before", "after"):
        r = RESULTS["ordering"][mode]
        print(f"--- Two partitions, two Writers, {mode} fix ({'no key' if mode == 'before' else 'key = entity_id'}) ---")
        for e, v in r["per_entity"].items():
            print(f"{e}  partitions={v['partitions']}  processed seq={v['processed_seq']}  in_order={v['in_order']}")
        print(f"messages processed={r['processed']}  listings out of order={r['entities_out_of_order']}\n")


if __name__ == "__main__":
    {"duplicate": duplicate, "consumer_death": consumer_death, "poison": poison, "ordering": ordering}[sys.argv[1]]()
