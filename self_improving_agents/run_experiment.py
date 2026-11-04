"""HW9 Part 4 experiment.

    python self_improving_agents/run_experiment.py demo        controlled revision and lesson reuse
    python self_improving_agents/run_experiment.py train       find repeated failure patterns on training_data
    python self_improving_agents/run_experiment.py validate    keep a candidate lesson only if validation_data does not regress
    python self_improving_agents/run_experiment.py revise      keep the rejected lesson as v1 and write the revised candidate
    python self_improving_agents/run_experiment.py test        final run of all four variants on test_data
    python self_improving_agents/run_experiment.py show        print the saved results
"""
import json
import sys
from collections import Counter
from pathlib import Path

from agents import DATA, PATTERNS, AnsweringAgent, EvaluatorAgent, LessonStore, load, run_question

RAW = Path(__file__).resolve().parent.parent / "reports" / "hw09" / "raw"
CANDIDATES = RAW / "part4_candidate_lessons.json"
CANDIDATES_V1 = RAW / "part4_candidate_lessons_v1.json"
VALIDATED = DATA / "lessons.json"
MIN_REPEATS = 2


def setup():
    reference = load("reference_data")
    return AnsweringAgent(reference), EvaluatorAgent(reference)


def save(name, data):
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def print_trail(r):
    print(f"Question: {r['question']}")
    print(f"Lessons loaded: {r['lessons_loaded'] or 'none'}")
    for t in r["trail"]:
        print(f"Attempt {t['attempt']} answer: {t['answer']}")
        print(f"  Evaluator: {t['result']} - {t['explanation']}")
        if t["feedback"]:
            print(f"  Feedback: {t['feedback']}")
    print(f"Attempts: {r['attempts']}  Final evaluation: {r['final_result']}\nFinal response: {r['final_answer']}\n", flush=True)


def demo():
    answering, evaluator = setup()
    train = {x["id"]: x for x in load("training_data")}
    print("=== 4.1 Controlled revision (initial answer is intentionally incomplete) ===\n")
    revision = run_question(train["tra_03"], answering, evaluator, forced_initial="The rent there is fairly reasonable for the area.")
    print_trail(revision)

    print("=== 4.2 A lesson created after one failed answer is reused on a later question ===\n")
    store = LessonStore(RAW / "part4_demo_lessons.json")
    store.lessons = []
    store.save()
    failed = run_question(train["tra_01"], answering, evaluator, store, max_attempts=1)
    print_trail(failed)
    lesson = store.add(failed["trail"][-1]["pattern"])
    print(f"Saved lesson: {json.dumps(lesson)}\n")
    later = run_question(train["tra_02"], answering, evaluator, store)
    print_trail(later)
    print(f"use_count after the later question: {store.lessons[0]['use_count']}")
    save("part4_demo.json", {"revision": revision, "failed": failed, "lesson": lesson, "later": later,
                             "use_count": store.lessons[0]["use_count"]})


def train():
    answering, evaluator = setup()
    rows = [run_question(item, answering, evaluator, None, max_attempts=2) for item in load("training_data")]
    patterns = Counter(r["trail"][0]["pattern"] for r in rows if r["trail"][0]["result"] == "REVISE")
    for r in rows:
        print(f"{r['id']} first={r['trail'][0]['result']} final={r['final_result']} attempts={r['attempts']}  {r['question']}", flush=True)
    keep = [k for k, n in patterns.items() if n >= MIN_REPEATS]
    print(f"\nFailure patterns on first attempts: {dict(patterns)}\nRepeated (>= {MIN_REPEATS}), become candidate lessons: {keep}")
    store = LessonStore(RAW / "part4_candidate_lessons_store.json")
    store.lessons = []
    store.save()
    for key in keep:
        store.add(key)
    save("part4_training.json", {"rows": rows, "patterns": dict(patterns)})
    save("part4_candidate_lessons.json", store.lessons)


def first_attempts(items, answering, evaluator, store):
    return {r["id"]: r for r in (run_question(item, answering, evaluator, store, max_attempts=1) for item in items)}


def validate():
    answering, evaluator = setup()
    items = load("validation_data")
    reference = load("reference_data")["checks"]
    before = first_attempts(items, answering, evaluator, None)
    kept, report = [], []
    for candidate in json.loads(CANDIDATES.read_text(encoding="utf-8")):
        store = LessonStore(RAW / "part4_validation_store.json")
        store.lessons = [dict(x, use_count=0) for x in kept] + [dict(candidate, use_count=0)]
        store.save()
        baseline = first_attempts(items, answering, evaluator, LessonStore_with(kept)) if kept else before
        after = first_attempts(items, answering, evaluator, store)
        was_pass = {k for k, r in baseline.items() if r["final_result"] == "PASS"}
        now_pass = {k for k, r in after.items() if r["final_result"] == "PASS"}
        regressions = sorted(was_pass - now_pass)
        unsupported = sorted(k for k, r in after.items() if reference[k]["kind"] == "unsupported" and r["final_result"] != "PASS")
        unsupported_before = {k for k, r in baseline.items() if reference[k]["kind"] == "unsupported" and r["final_result"] != "PASS"}
        accepted = len(now_pass) >= len(was_pass) and not regressions and set(unsupported) <= unsupported_before
        report.append({"lesson_id": candidate["lesson_id"], "pattern": candidate["pattern_key"], "passes_before": len(was_pass),
                       "passes_after": len(now_pass), "fixed": sorted(now_pass - was_pass), "regressions": regressions,
                       "unsupported_after": unsupported, "kept": accepted,
                       "before": {k: r["final_answer"] for k, r in baseline.items()}, "after": {k: r["final_answer"] for k, r in after.items()}})
        print(f"{candidate['lesson_id']} {candidate['pattern_key']}: passes {len(was_pass)} -> {len(now_pass)}, fixed {report[-1]['fixed']}, "
              f"regressions {regressions}, unsupported {unsupported} -> {'KEEP' if accepted else 'REMOVE'}", flush=True)
        if accepted:
            kept.append(candidate)
    VALIDATED.write_text(json.dumps([dict(x, use_count=0) for x in kept], indent=2), encoding="utf-8")
    save("part4_validation.json", report)


def revise():
    """The first lesson failed validation. Keep it and its results, then write the revised lesson as the candidate."""
    first = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    save("part4_candidate_lessons_v1.json", first)
    save("part4_validation_v1.json", json.loads((RAW / "part4_validation.json").read_text(encoding="utf-8")))
    save("part4_test_v1.json", json.loads((RAW / "part4_test.json").read_text(encoding="utf-8")))
    revised = [{**x, "correction": PATTERNS[x["pattern_key"]]["correction"], "avoid": PATTERNS[x["pattern_key"]].get("avoid", [])} for x in first]
    save("part4_candidate_lessons.json", revised)
    print(json.dumps(revised, indent=2))


def LessonStore_with(lessons):
    store = LessonStore(RAW / "part4_validation_base.json")
    store.lessons = [dict(x, use_count=0) for x in lessons]
    store.save()
    return store


def variant(name, items, answering, evaluator, store, max_attempts):
    rows = [run_question(item, answering, evaluator, store, max_attempts) for item in items]
    correct = sum(r["final_result"] == "PASS" for r in rows)
    summary = {"variant": name, "correct": correct, "incorrect": len(rows) - correct,
               "average_attempts": round(sum(r["attempts"] for r in rows) / len(rows), 2),
               "average_latency_ms": round(sum(r["latency_ms"] for r in rows) / len(rows), 1)}
    print(json.dumps(summary), flush=True)
    return {"summary": summary, "rows": rows}


def test():
    answering, evaluator = setup()
    items = load("test_data")
    results = {"Baseline": variant("Baseline", items, answering, evaluator, None, 1),
               "Evaluator Repair": variant("Evaluator Repair", items, answering, evaluator, None, 2)}
    # Lesson Memory uses the lesson as first learned, before any validation
    all_lessons = LessonStore_with(json.loads(CANDIDATES_V1.read_text(encoding="utf-8")))
    results["Lesson Memory"] = variant("Lesson Memory", items, answering, evaluator, all_lessons, 2)
    validated = LessonStore_with(json.loads(VALIDATED.read_text(encoding="utf-8")))
    results["Validated Improvement"] = variant("Validated Improvement", items, answering, evaluator, validated, 2)
    # lessons.json keeps the validated lessons; use_count records their reuse on the final run
    VALIDATED.write_text(json.dumps(validated.lessons, indent=2), encoding="utf-8")
    save("part4_test.json", results)
    show()


def show():
    results = json.loads((RAW / "part4_test.json").read_text(encoding="utf-8"))
    print(f"{'Variant':24}{'Correct':9}{'Incorrect':11}{'Avg attempts':14}{'Avg latency (ms)':>16}")
    for r in results.values():
        s = r["summary"]
        print(f"{s['variant']:24}{s['correct']:<9}{s['incorrect']:<11}{s['average_attempts']:<14}{s['average_latency_ms']:>16.1f}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"demo": demo, "train": train, "validate": validate, "revise": revise, "test": test, "show": show}[sys.argv[1]]()
