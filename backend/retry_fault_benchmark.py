"""Part 3: deterministic retry/fault-injection experiment (150 calls)."""
from __future__ import annotations

import json
import random
import statistics
import time
from pathlib import Path

VERIFY_SEED = 266758
RATES = (0.0, 0.2, 0.5)
CALLS_PER_RATE = 50
MAX_RETRIES = 2


def run_call(rng: random.Random, rate: float, call_id: int) -> dict:
    started = time.perf_counter()
    attempts = 0
    errors = []
    while attempts <= MAX_RETRIES:
        attempts += 1
        if rng.random() >= rate:
            latency = (time.perf_counter() - started) * 1000
            return {"rate": rate, "call_id": call_id, "success": True, "attempts": attempts, "latency_ms": round(latency, 3), "error": None}
        errors.append("injected storage failure")
        if attempts <= MAX_RETRIES:
            time.sleep(0.001 * (2 ** (attempts - 1)))
    latency = (time.perf_counter() - started) * 1000
    return {"rate": rate, "call_id": call_id, "success": False, "attempts": attempts, "latency_ms": round(latency, 3), "error": errors[-1]}


def percentile(values: list[float], p: float) -> float:
    values = sorted(values)
    index = max(0, min(len(values) - 1, int(round((p / 100) * (len(values) - 1)))))
    return values[index]


def main() -> None:
    out_dir = Path("reports/hw05/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(VERIFY_SEED)
    rows = [run_call(rng, rate, i) for rate in RATES for i in range(1, CALLS_PER_RATE + 1)]
    summaries = []
    for rate in RATES:
        group = [r for r in rows if r["rate"] == rate]
        latencies = [r["latency_ms"] for r in group]
        summaries.append({"injected_failure_rate": rate, "calls": len(group), "success_rate": round(sum(r["success"] for r in group) / len(group), 4), "mean_latency_ms": round(statistics.mean(latencies), 3), "p99_latency_ms": round(percentile(latencies, 99), 3)})
    (out_dir / "fault_injection_results.json").write_text(json.dumps({"seed": VERIFY_SEED, "max_retries": MAX_RETRIES, "rows": rows, "summaries": summaries}, indent=2), encoding="utf-8")
    print(json.dumps(summaries, indent=2))
    print(f"Saved {len(rows)} records to {out_dir / 'fault_injection_results.json'}")


if __name__ == "__main__":
    main()
