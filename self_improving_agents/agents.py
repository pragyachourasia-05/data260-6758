"""HW9 Part 4: Answering Agent, Evaluator Agent and the lesson store."""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
sys.path.insert(0, str(ROOT))
MAX_ATTEMPTS = 2
REFUSAL = re.compile(r"not available|not in the|no information|(does|do) not (include|list|mention|say|state|specify|provide|contain)|"
                     r"(doesn't|don't) (include|list|mention|say|state|specify|provide|contain)|do not have|don't have|"
                     r"(cannot|can't|could not|couldn't) (answer|find|confirm|determine)|no record|not provided|not specified|"
                     r"not listed|not mentioned|not stated|unable to|not able to|outside", re.I)

INVENTED = re.compile(r"\b(studio|single[- ]family|multi[- ]family|\d[- ]bedroom|one[- ]bedroom|two[- ]bedroom|bedrooms?|bathrooms?|sq\.? ?ft|"
                      r"square f\w+|townhouse|townhome|condo\w*|duplex|furnished|renovated|spacious|cozy|luxury)\b", re.I)
DENIAL = re.compile(r"\bthere (is|are) no (?!information|record|data|mention|detail)|\b(is|are) not (allowed|included|permitted)\b|^no\b", re.I | re.M)
LISTING_DENIED = re.compile(r"(no|any|find|a) (matching |such )?(listing|record)s? (at|for|on)\b|information (on|about) a listing|"
                            r"listing .{0,30}(does not|doesn't) exist", re.I)

# What the Evaluator can recognise, and the reusable lesson each failure pattern turns into.
PATTERNS = {
    "unsupported_answer": {
        "failure_pattern": "The answer states something the listing records do not contain.",
        "correction": "If the listing record does not contain the fact, or the question is not about a listing, say the "
                      "information is not available in the records. Do not guess.",
        "keywords": ["allowed", "allow", "include", "included", "includes", "there", "have", "capital", "who", "what is the tallest"]},
    "wrong_calculation": {
        "failure_pattern": "The total or difference is wrong or missing.",
        "correction": "Work from the monthly rents in the records. Totals: rent times months. Combined rent: add the rents. "
                      "Difference over several months: subtract the rents, then multiply by the months. Split: divide by the people. "
                      "Finish with the final dollar amount as a plain number.",
        "keywords": ["total", "months", "cheaper", "cheapest", "less", "lower", "lowest", "difference", "combined", "together", "split", "more"]},
    "added_detail": {
        "failure_pattern": "The answer adds property details that the listing record does not list.",
        "correction": "Answer the question in a full sentence using the values in the record. Do not add property descriptions "
                      "the record does not list, such as studio, single-family, bedrooms or spacious.",
        "keywords": ["rent", "type", "kind", "house", "apartment", "units", "property"],
        # validation showed this lesson hurts comparisons and two-part questions, so it only loads on plain lookups
        "avoid": ["cheaper", "cheapest", "lower", "less", "more", "total", "combined", "split", "months", "allowed", "included", "include", "have"]},
    "missing_fact": {
        "failure_pattern": "The answer leaves out a value the question asked for.",
        "correction": "Answer every part of the question and state each value exactly as it appears in the listing record.",
        "keywords": ["and", "both", "list", "tell"]},
}


class LessonStore:
    def __init__(self, path: Path = DATA / "lessons.json"):
        self.path = path
        self.lessons = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def save(self) -> None:
        self.path.write_text(json.dumps(self.lessons, indent=2), encoding="utf-8")

    def add(self, pattern_key: str) -> dict:
        for lesson in self.lessons:
            if lesson["pattern_key"] == pattern_key:
                return lesson
        p = PATTERNS[pattern_key]
        lesson = {"lesson_id": f"lesson_{len(self.lessons) + 1:03d}", "failure_pattern": p["failure_pattern"],
                  "correction": p["correction"], "created_at": date.today().isoformat(), "use_count": 0,
                  "pattern_key": pattern_key, "keywords": p["keywords"], "avoid": p.get("avoid", [])}
        self.lessons.append(lesson)
        self.save()
        return lesson

    def relevant(self, question: str) -> list[dict]:
        q = question.lower()
        has = lambda words: any(re.search(rf"\b{re.escape(k)}\b", q) for k in words)  # noqa: E731
        return [x for x in self.lessons if has(x["keywords"]) and not has(x.get("avoid", []))]

    def mark_used(self, lessons: list[dict]) -> None:
        for lesson in lessons:
            lesson["use_count"] += 1
        self.save()


class AnsweringAgent:
    SYSTEM = ("You answer questions for a rental housing listings assistant, in at most 3 short sentences, using the listing "
              "records you are given.")

    def __init__(self, reference: dict):
        from src.model_client import ModelClient

        self.client = ModelClient(model="llama3.2:3b", temperature=0.0, verbose=False, seed=6758, num_predict=160)
        self.records = {int(k): v for k, v in reference["listings"].items()}

    def context(self, question: str) -> str:
        rows = [self.records[int(n)] for n in re.findall(r"\b(\d{3}) Research Avenue", question) if int(n) in self.records]
        if not rows:
            return "No matching listing record."
        return "\n".join(f"{r['address']}: monthly rent ${r['monthly_rent']}, property type {r['property_type']}, "
                         f"available units {r['available_units']}." for r in rows)

    def answer(self, question: str, lessons: list[dict] | None = None, feedback: str = "", previous: str = "") -> str:
        system = self.SYSTEM
        if lessons:
            system += "\nLessons from past mistakes:\n" + "\n".join(f"- {x['correction']}" for x in lessons)
        prompt = f"Listing records:\n{self.context(question)}\n\nQuestion: {question}"
        if feedback:
            prompt += f"\n\nYour previous answer: {previous}\nEvaluator feedback: {feedback}\nWrite a corrected answer."
        return self.client.complete([{"role": "system", "content": system}, {"role": "user", "content": prompt}])["text"].strip()


class EvaluatorAgent:
    """Checks an answer against reference_data.json; the verdict comes from the facts, not from the model."""

    def __init__(self, reference: dict):
        self.checks = reference["checks"]

    def evaluate(self, question_id: str, answer: str) -> dict:
        check = self.checks[question_id]
        kind, refused = check["kind"], REFUSAL.search(answer)
        if check.get("has_listing") and LISTING_DENIED.search(answer):
            return revise("unsupported_answer", "The answer says the listing is missing, but the record exists.",
                          "The listing record is given above. Use it.")
        if kind == "unsupported":
            if not refused or DENIAL.search(answer):
                return revise("unsupported_answer", "The reference data has no such fact, so a yes or no here is unsupported.",
                              "The listing records do not contain this information. Say that it is not available in the records.")
        else:
            low = answer.lower()
            missing = [label for options, label in zip(check["required_any_of"], check["facts"], strict=True)
                       if not any(re.search(rf"(?<![\d,]){re.escape(o.lower())}(?!\d|,\d)", low) for o in options)]
            if check.get("forbid") and re.search(check["forbid"], answer, re.I):
                missing.append(check["facts"][0])
            if kind == "mixed" and (not refused or DENIAL.search(answer)):
                return revise("unsupported_answer", f"Missing or wrong: {'; '.join(missing + [check['unsupported']])}.",
                              f"Fix these using the records: {'; '.join(missing + [check['unsupported']])}. "
                              "Say the records do not contain anything they do not list.")
            if missing:
                return revise("wrong_calculation" if kind in ("calc", "compare") else "missing_fact",
                              f"Missing or wrong: {'; '.join(missing)}.", f"Correct the answer using these reference facts: {'; '.join(missing)}.")
        invented = INVENTED.search(answer)
        if invented:
            return revise("added_detail", f"The answer says '{invented.group(0)}', which is not in the listing record.",
                          f"Remove '{invented.group(0)}'. State only the values in the listing record.")
        return {"result": "PASS", "explanation": "The answer matches the reference data and adds nothing unsupported.", "feedback": "", "pattern": None}


def revise(pattern: str, explanation: str, feedback: str) -> dict:
    return {"result": "REVISE", "explanation": explanation, "feedback": feedback, "pattern": pattern}


def run_question(item: dict, answering: AnsweringAgent, evaluator: EvaluatorAgent, store: LessonStore | None = None,
                 max_attempts: int = MAX_ATTEMPTS, forced_initial: str | None = None) -> dict:
    """Answer, evaluate, and revise once if needed. Stops after max_attempts."""
    start = time.perf_counter()
    lessons = store.relevant(item["question"]) if store else []
    if store and lessons:
        store.mark_used(lessons)
    trail, answer, feedback = [], "", ""
    for attempt in range(1, max_attempts + 1):
        if attempt == 1 and forced_initial is not None:
            answer = forced_initial
        else:
            answer = answering.answer(item["question"], lessons, feedback, answer)
        verdict = evaluator.evaluate(item["id"], answer)
        trail.append({"attempt": attempt, "answer": answer, **verdict})
        if verdict["result"] == "PASS":
            break
        feedback = verdict["feedback"]
    return {"id": item["id"], "question": item["question"], "lessons_loaded": [x["lesson_id"] for x in lessons],
            "attempts": len(trail), "final_answer": answer, "final_result": trail[-1]["result"], "trail": trail,
            "latency_ms": round((time.perf_counter() - start) * 1000, 1)}


def load(name: str):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
