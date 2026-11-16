"""HW10 judge: DeepEval GEval with a local Ollama model, scores on a 1-5 scale.

Settings (kept the same for Part 2 and Part 3):
    model llama3.2:3b through Ollama (http://localhost:11434), temperature 0, seed 6758
    the rubric pins the score to whole numbers 1-5; GEval returns score/10, so judge score = round(score * 10)
"""
from __future__ import annotations

import math
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")  # no usage data leaves the laptop

from deepeval.metrics import GEval  # noqa: E402
from deepeval.metrics.g_eval import Rubric  # noqa: E402
from deepeval.models import OllamaModel  # noqa: E402
from deepeval.test_case import LLMTestCase, LLMTestCaseParams  # noqa: E402

JUDGE_MODEL = os.getenv("JUDGE_MODEL", "llama3.2:3b")
JUDGE_URL = os.getenv("JUDGE_URL", "http://localhost:11434")
JUDGE_SEED = 6758
TIMEOUT_S = float(os.getenv("JUDGE_TIMEOUT_S", "180"))
_pool = ThreadPoolExecutor(max_workers=1)

RUBRIC = [
    Rubric(score_range=(1, 1), expected_outcome="Very poor: wrong, off-topic or of no use."),
    Rubric(score_range=(2, 2), expected_outcome="Poor: mostly unhelpful or has a clear mistake."),
    Rubric(score_range=(3, 3), expected_outcome="OK: partly answers; misses important parts or is padded."),
    Rubric(score_range=(4, 4), expected_outcome="Good: correct and useful with small issues."),
    Rubric(score_range=(5, 5), expected_outcome="Excellent: correct, complete, clear and to the point."),
]

HELPFULNESS_STEPS = [
    "Read the question in 'input'. If listing facts are included, they are the true values for that listing.",
    "Check that 'actual output' answers the question that was asked and stays on topic.",
    "Check that any rent, property type or unit count in 'actual output' matches the listing facts.",
    "Penalize made-up facts, missing key information, and long padding that does not help a renter.",
]
PLAN_STEPS = [
    "Read the question in 'input' and the plan steps in 'actual output'.",
    "Check that the steps are specific to this question and would lead a writer to a correct, complete answer.",
    "Penalize steps that are vague, generic, repeated, or that skip the facts the question needs.",
]


def judge_model() -> OllamaModel:
    return OllamaModel(model=JUDGE_MODEL, base_url=JUDGE_URL, temperature=0,
                       generation_kwargs={"seed": JUDGE_SEED})


def metric(name: str, steps: list[str], model: OllamaModel | None = None) -> GEval:
    return GEval(name=name, evaluation_steps=steps, rubric=RUBRIC,
                 evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
                 model=model or judge_model(), async_mode=False)


def to_scale(raw: float | None) -> int | None:
    if raw is None:
        return None
    return max(1, min(5, math.floor(raw * 10 + 0.5)))  # halves round up (Python's round(2.5) would give 2)


def score(m: GEval, question: str, output: str, facts: str = "", timeout: float = TIMEOUT_S) -> dict:
    """Score one output. Bounded by a timeout so an unavailable judge cannot hang the run."""
    text_in = question + (f"\nListing facts: {facts}" if facts else "")
    case = LLMTestCase(input=text_in, actual_output=output or "(empty)")
    future = _pool.submit(m.measure, case)
    try:
        future.result(timeout=timeout)
    except FutureTimeout:
        return {"score": None, "raw": None, "reason": None, "error": f"judge timed out after {timeout:.0f}s"}
    except Exception as exc:  # judge down, bad JSON from the judge, ...
        return {"score": None, "raw": None, "reason": None, "error": f"{type(exc).__name__}: {exc}"[:300]}
    return {"score": to_scale(m.score), "raw": m.score, "reason": (m.reason or "").strip(), "error": None}
