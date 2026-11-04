"""Builds reports/hw09/METRICS.md and RUN_LOG.txt from the saved run results.

    python backend/make_hw09_metrics.py
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports" / "hw09"
RAW = REPORTS / "raw"
DATA = ROOT / "self_improving_agents" / "data"
MISS_COST = 0.01  # three LLM calls per miss, assumed hosted price, rounded up
FALSE_HIT_COST = 2.00  # about 6 minutes of a $20/hour support person fixing one wrong answer


def load(name):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


def total_cost(summary):
    return round(summary["misses"] * MISS_COST + summary["false_hits"] * FALSE_HIT_COST, 2)


def metrics():
    counter, part2, sweep, stale = load("part1_counter.json"), load("part2_semantic.json"), load("part3_sweep.json"), load("part3_stale.json")
    test, validation, demo = load("part4_test.json"), load("part4_validation.json"), load("part4_demo.json")
    rows = part2 if isinstance(part2, list) else part2["rows"]
    hits = [r for r in rows if r["is_cached"]]
    misses = [r for r in rows if not r["is_cached"]]
    avg = lambda group: sum(r["latency_ms"] for r in group) / len(group)  # noqa: E731
    md = ["# HW9 Metrics", "", "## Part 1 - Counter", "", f"Redis `{counter['redis_key']}` = {counter['redis_count']}, MySQL view_count = "
          f"{counter['database_view_count']} (last sync at 20).", "", "## Part 2 - Semantic cache, threshold 0.85", "",
          "| Queries | Hits | Hit rate | Avg latency cached (ms) | Avg latency not cached (ms) |", "| --- | --- | --- | --- | --- |",
          f"| {len(rows)} | {len(hits)} | {len(hits) / len(rows):.0%} | {avg(hits):.1f} | {avg(misses):.1f} |", "",
          "## Part 3 - Threshold sweep (40 cases)", "",
          f"Cost per 40 queries = misses x ${MISS_COST:.2f} + false hits x ${FALSE_HIT_COST:.2f}.", "",
          "| Threshold | Hit rate | False-hit rate | Mean latency (ms) | Total cost |", "| --- | --- | --- | --- | --- |"]
    for t, d in sweep.items():
        s = d["summary"]
        md.append(f"| {float(t):.2f} | {s['hit_rate']:.1%} | {s['false_hit_rate']:.1%} | {s['mean_latency_ms']:.1f} | ${total_cost(s):.2f} |")
    md += ["", f"Stale test: rent {stale['original_rent']} -> {stale['new_rent']}; version check off served the old rent "
           f"({stale['stale_answer_has_old_rent']}); version check on dropped it and regenerated ({stale['fresh_answer_has_new_rent']}).",
           "", "## Part 4 - Validation of candidate lessons", "", "| Lesson | Pattern | First-attempt passes before | After | Fixed | Regressions | Kept |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    md += [f"| {r['lesson_id']} | {r['pattern']} | {r['passes_before']} | {r['passes_after']} | {', '.join(r['fixed']) or '-'} | "
           f"{', '.join(r['regressions']) or '-'} | {r['kept']} |" for r in validation]
    md += ["", "## Part 4 - Test set results", "", "| Variant | Correct | Incorrect | Average attempts | Average latency (ms) |", "| --- | --- | --- | --- | --- |"]
    md += [f"| {r['summary']['variant']} | {r['summary']['correct']} | {r['summary']['incorrect']} | {r['summary']['average_attempts']} | "
           f"{r['summary']['average_latency_ms']:.1f} |" for r in test.values()]
    md += ["", f"Lesson reuse demo: `{demo['lesson']['lesson_id']}` loaded on: {demo['later']['question']}", ""]
    (REPORTS / "METRICS.md").write_text("\n".join(md), encoding="utf-8")


def section(title):
    return f"\n{'=' * 100}\n{title}\n{'=' * 100}\n"


def trail(r):
    out = [f"Question: {r['question']}\nLessons loaded: {r['lessons_loaded'] or 'none'}\n"]
    for t in r["trail"]:
        out.append(f"Attempt {t['attempt']}: {t['answer']}\n  {t['result']} - {t['explanation']}\n")
    out.append(f"Final: {r['final_result']} after {r['attempts']} attempt(s)\n\n")
    return "".join(out)


def runlog():
    out = [f"DATA-260 HW9 RUN_LOG - Pragya Chourasia - SID4 6758 - built {datetime.now():%Y-%m-%d %H:%M:%S}\n"]
    ps = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Image}}\t{{.Status}}"], capture_output=True, text=True).stdout
    out += [section("docker ps"), ps, section("Part 1 - counter"), json.dumps(load("part1_counter.json"), indent=2) + "\n"]
    out += [section("Part 2 - cache log with timestamps (raw/part2_qa_api.log)"), (RAW / "part2_qa_api.log").read_text(encoding="utf-8")]
    out.append(section("Part 3 - sweep, one line per case"))
    for t, d in load("part3_sweep.json").items():
        out.append(f"\nthreshold {t}: {json.dumps(d['summary'])}\n")
        out += [f"  {r['id']} {'HIT ' if r['is_cached'] else 'miss'} sim={r['similarity']:<7} false_hit={r['false_hit']!s:5} {r['question']}"
                f"{' <- ' + r['cached_query'] if r['cached_query'] else ''}\n" for r in d["rows"]]
    out += [section("Part 3 - stale answer test"), json.dumps(load("part3_stale.json"), indent=2) + "\n"]
    demo = load("part4_demo.json")
    out += [section("Part 4 - controlled revision"), trail(demo["revision"]), section("Part 4 - lesson created and reused"), trail(demo["failed"]),
            json.dumps(demo["lesson"], indent=2) + "\n\n", trail(demo["later"])]
    out += [section("Part 4 - training"), json.dumps(load("part4_training.json")["patterns"]) + "\n"]
    out += [trail(r) for r in load("part4_training.json")["rows"]]
    out += [section("Part 4 - validation"), json.dumps(load("part4_validation.json"), indent=2) + "\n", section("Part 4 - test")]
    for name, r in load("part4_test.json").items():
        out.append(f"\n--- {name}: {json.dumps(r['summary'])}\n")
        out += [trail(x) for x in r["rows"]]
    (REPORTS / "RUN_LOG.txt").write_text("".join(out), encoding="utf-8")


if __name__ == "__main__":
    metrics()
    runlog()
    print("METRICS.md and RUN_LOG.txt written")
