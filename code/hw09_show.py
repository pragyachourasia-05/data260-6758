"""Print saved HW9 results in the terminal.

    python code/hw09_show.py part2 | log | sweep | falsehit | stale | revision | lesson | training | validation | test | lessons
"""
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "reports" / "hw09" / "raw"
DATA = ROOT / "self_improving_agents" / "data"
MISS_COST, FALSE_HIT_COST = 0.01, 2.00
WIDTH = 170


def load(name):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


def wrap(label, text, width=WIDTH):
    text = " ".join(str(text).split())
    print(textwrap.fill(text, width, initial_indent=label, subsequent_indent=" " * len(label)))


def part2():
    data = load("part2_semantic.json")
    rows = data if isinstance(data, list) else data["rows"]
    print(f"{'#':3}{'Kind':17}{'Cached':8}{'Similarity':12}{'Latency ms':12}Query")
    for n, r in enumerate(rows, 1):
        print(f"{n:<3}{r['kind']:17}{str(r['is_cached']):8}{r['similarity']:<12.4f}{r['latency_ms']:<12.1f}{r['question']}")
    hits = [r for r in rows if r["is_cached"]]
    misses = [r for r in rows if not r["is_cached"]]
    print(f"\nHit rate: {len(hits)}/{len(rows)} = {len(hits) / len(rows):.0%}")
    print(f"Average latency cached:     {sum(r['latency_ms'] for r in hits) / len(hits):10.1f} ms")
    print(f"Average latency not cached: {sum(r['latency_ms'] for r in misses) / len(misses):10.1f} ms")


def log():
    for line in (RAW / "part2_qa_api.log").read_text(encoding="utf-8").splitlines():
        if "CACHE" in line:
            print(line[:WIDTH])


def sweep():
    print(f"Total cost per 40 queries = misses x ${MISS_COST:.2f} + false hits x ${FALSE_HIT_COST:.2f}\n")
    print(f"{'Threshold':11}{'Hits':6}{'Misses':8}{'False hits':12}{'Hit rate':10}{'False-hit rate':16}{'Mean latency (ms)':19}Total cost")
    for t, d in load("part3_sweep.json").items():
        s = d["summary"]
        cost = s["misses"] * MISS_COST + s["false_hits"] * FALSE_HIT_COST
        print(f"{float(t):<11.2f}{s['hits']:<6}{s['misses']:<8}{s['false_hits']:<12}{s['hit_rate']:<10.1%}{s['false_hit_rate']:<16.1%}{s['mean_latency_ms']:<19.1f}${cost:.2f}")


def falsehit():
    data = load("part3_sweep.json")
    memo = load("part3_agent_memo.json")
    r = next(x for x in data["0.85"]["rows"] if x["id"] == "m01")
    print(f"Threshold 0.85, case {r['id']} (similar but different)\n")
    wrap("New query:      ", r["question"])
    wrap("Matched query:  ", r["cached_query"])
    print(f"Similarity:     {r['similarity']}\n")
    wrap("Cached answer returned: ", r["answer"])
    print()
    wrap("Correct answer (agents, no cache): ", memo[r["question"]]["answer"])
    print("\nFalse hits at 0.95:")
    for x in data["0.95"]["rows"]:
        if x["false_hit"]:
            print(f"  {x['id']} sim={x['similarity']}  {x['question']}  <-  {x['cached_query']}")
    low = min((x for x in data["0.85"]["rows"] if x["group"] == "paraphrase"), key=lambda x: x["similarity"] if x["cached_key"] == x["answer_key"] else 2)
    print(f"\nLowest correct paraphrase hit: {low['id']} sim={low['similarity']}  {low['question']}")


def stale():
    s = load("part3_stale.json")
    print(f"Query: {s['question']}\n")
    wrap("1. Cold cache, agents ran. ", f"latency {s['cold']['latency_ms']} ms. {s['cold']['answer']}")
    print(f"\n2. UPDATE listings SET monthly_rent = '{s['new_rent']}' WHERE id = {s['listing_id']}  (was {s['original_rent']})\n")
    wrap("3. Version check OFF: STALE HIT. ", f"is_cached={s['stale_hit']['is_cached']} similarity={s['stale_hit']['similarity']}. {s['stale_hit']['answer']}")
    print()
    wrap("4. Version check ON: entry dropped. ", f"is_cached={s['after_invalidation']['is_cached']} stale_dropped={s['after_invalidation']['stale_dropped']} "
         f"latency {s['after_invalidation']['latency_ms']} ms. {s['after_invalidation']['answer']}")
    print()
    wrap("5. Asked again. ", f"is_cached={s['repeat']['is_cached']} latency {s['repeat']['latency_ms']} ms. {s['repeat']['answer']}")
    print(f"\nRent restored to {s['original_rent']} after the test.")


def trail(r):
    wrap("Question: ", r["question"])
    print(f"Lessons loaded: {r['lessons_loaded'] or 'none'}")
    for t in r["trail"]:
        wrap(f"Attempt {t['attempt']} answer: ", t["answer"])
        wrap(f"  Evaluator: {t['result']} - ", t["explanation"])
        if t["feedback"]:
            wrap("  Feedback: ", t["feedback"])
    print(f"Attempts: {r['attempts']}   Final evaluation: {r['final_result']}\n")


def revision():
    print("Controlled failing case: the first answer is forced to be incomplete.\n")
    trail(load("part4_demo.json")["revision"])


def lesson():
    d = load("part4_demo.json")
    trail(d["failed"])
    print("Saved lesson:")
    print(json.dumps({k: d["lesson"][k] for k in ("lesson_id", "failure_pattern", "correction", "created_at")}, indent=2))
    print()
    trail(d["later"])
    print(f"use_count after the later question: {d['use_count']}")


def training():
    d = load("part4_training.json")
    for r in d["rows"]:
        print(f"{r['id']} first={r['trail'][0]['result']:7} final={r['final_result']:7} attempts={r['attempts']}  {r['question']}")
    print(f"\nFailure patterns on first attempts: {d['patterns']}")


def validation():
    for name, title in (("part4_validation_v1.json", "First lesson"), ("part4_validation.json", "Revised lesson")):
        for r in load(name):
            print(f"{title} - {r['lesson_id']} {r['pattern']}: first-attempt passes {r['passes_before']} -> {r['passes_after']}, fixed {r['fixed']}, "
                  f"regressions {r['regressions']}, still unsupported {r['unsupported_after']} -> {'KEEP' if r['kept'] else 'REMOVE'}")


def test():
    results = load("part4_test.json")
    print(f"{'Variant':24}{'Correct':9}{'Incorrect':11}{'Avg attempts':14}Avg latency (ms)")
    for r in results.values():
        s = r["summary"]
        print(f"{s['variant']:24}{s['correct']:<9}{s['incorrect']:<11}{s['average_attempts']:<14}{s['average_latency_ms']:.1f}")


def lessons():
    print((DATA / "lessons.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    globals()[sys.argv[1]]()
