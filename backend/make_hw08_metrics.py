"""Builds reports/hw08/METRICS.md and raw/part3_log_excerpts.txt from the saved failure-test results.

    python backend/make_hw08_metrics.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports" / "hw08"
RAW = REPORTS / "raw"
LOGS = RAW / "part3"


def lines(name, keep=None):
    path = LOGS / f"{name}.log"
    text = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return [x for x in text if keep is None or any(k in x for k in keep)]


def main():
    r = json.loads((RAW / "part3_results.json").read_text(encoding="utf-8"))
    demo = json.loads((RAW / "part1_demo.json").read_text(encoding="utf-8"))
    final = json.loads((RAW / "part2_final.json").read_text(encoding="utf-8"))
    dup, kill, poison, order = r["duplicate"], r["consumer_death"], r["poison"], r["ordering"]

    def order_cell(side):
        out = [e for e, v in side["per_entity"].items() if not v["in_order"]]
        split = [e for e, v in side["per_entity"].items() if len(v["partitions"]) > 1]
        return (f"{side['processed']} processed, {len(split)} of 3 listings split across partitions, "
                f"{side['entities_out_of_order']} of 3 out of order" + (f" ({', '.join(out)})" if out else ""))

    table = [
        ("Duplicate delivery",
         f"Replay ran every agent again: {dup['before']['agent_runs']['reviewer']} Reviewer runs, "
         f"{dup['before']['messages_in_final']} messages in s6758_final",
         f"Replay skipped by the Planner: {dup['after']['duplicates_skipped']} duplicate skipped, "
         f"{dup['after']['messages_in_final']} message in s6758_final"),
        ("Consumer killed mid-work",
         f"Offset already committed at the kill ({kill['before']['committed_offset_when_killed']}); message not "
         f"redelivered, {kill['before']['drafts_in_topic']} drafts, so the work was lost",
         f"No offset committed at the kill; message redelivered after restart, "
         f"{kill['after']['drafts_in_topic']} draft, offset then committed "
         f"({kill['after']['committed_offset_at_end']})"),
        ("Poison message",
         f"Writer crashed {poison['before']['crashes']} times on the same message; later message processed: "
         f"{poison['before']['good_message_processed']}",
         f"{poison['after']['failed_attempts_logged']} attempts, {poison['after']['dead_letter_messages']} message in "
         f"s6758_dead_letter, {poison['after']['crashes']} crashes; later message processed: "
         f"{poison['after']['good_message_processed']}"),
        ("Two partitions/two consumers", order_cell(order["before"]), order_cell(order["after"])),
    ]

    md = ["# HW8 Metrics", "", "## Part 1 - CREATE_LISTING and GET_LISTING", "", "| Check | Result |", "| --- | --- |"]
    md += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in demo["checks"].items()]
    md += ["", "| Error case | Error returned | correlation_id preserved |", "| --- | --- | --- |"]
    md += [f"| {e['operation']} | {e['response'].get('error')} | "
           f"{e['response'].get('correlation_id') == e['sent_correlation_id']} |" for e in demo["errors"]]
    md += ["", "## Part 2 - Message journey", "", f"correlation_id: `{final['correlation_id']}`", "",
           "| Stage | Time (UTC) |", "| --- | --- |"]
    md += [f"| {t['agent']} | {t['at']} |" for t in final["trace"]]
    md += ["", f"Final status: **{final['status']}**", "", "## Part 3 - Failure table", "",
           "| Failure scenario | Before fix | After fix |", "| --- | --- | --- |"]
    md += [f"| {a} | {b} | {c} |" for a, b, c in table]
    md += ["", "## Part 3 - Ordering runs (VERIFY_SEED 266758, 20 messages)", "",
           "| Run | Listing | Partitions | Processed seq | In order |", "| --- | --- | --- | --- | --- |"]
    for mode in ("before", "after"):
        for e, v in order[mode]["per_entity"].items():
            md.append(f"| {mode} | {e} | {v['partitions']} | {v['processed_seq']} | {v['in_order']} |")
    (REPORTS / "METRICS.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    ex = []
    for title, name, keep in [
        ("Duplicate delivery - before fix", "duplicate_before_planner", [dup["before"]["correlation_id"]]),
        ("Duplicate delivery - after fix", "duplicate_after_planner", [dup["after"]["correlation_id"]]),
        ("Consumer killed - before fix", "consumer_death_before_writer",
         [kill["before"]["correlation_id"], "listening"]),
        ("Consumer killed - after fix", "consumer_death_after_writer",
         [kill["after"]["correlation_id"], "listening", "offset committed"]),
        ("Poison message - before fix", "poison_before_writer", ["poison-", "good-", "listening"]),
        ("Poison message - after fix", "poison_after_writer", ["poison-", "good-", "dead_letter", "offset committed"]),
    ]:
        ex += [f"--- {title} ---"] + lines(name, keep) + [""]
    ex += ["--- Ordering - processed sequence per listing ---"]
    for mode in ("before", "after"):
        for e, v in order[mode]["per_entity"].items():
            ex.append(f"{mode}: {e} partitions={v['partitions']} seq={v['processed_seq']} in_order={v['in_order']}")
    (RAW / "part3_log_excerpts.txt").write_text("\n".join(ex) + "\n", encoding="utf-8")
    print("wrote METRICS.md and raw/part3_log_excerpts.txt")


if __name__ == "__main__":
    main()
