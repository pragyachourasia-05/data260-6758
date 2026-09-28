import json
import statistics
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "reports" / "hw04" / "raw"
BASE_URL = "http://localhost:8458"
RUNS = 30
PAGE_SIZES = [10, 50, 200]
ENDPOINTS = {
    "naive": "/bench/listings-naive",
    "fixed": "/bench/listings-fixed",
}


def request_once(path):
    request = Request(BASE_URL + path, method="GET")
    started = time.perf_counter()
    with urlopen(request, timeout=120) as response:
        body = response.read()
        elapsed_ms = (time.perf_counter() - started) * 1000
        sql_count = int(response.headers.get("X-SQL-Count", "-1"))
        status = response.status

    return {
        "status": status,
        "sql_statements": sql_count,
        "latency_ms": round(elapsed_ms, 3),
        "response_bytes": len(body),
    }


def percentile(values, percentile):
    values = sorted(values)
    if not values:
        return 0.0
    index = (len(values) - 1) * percentile / 100
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    weight = index - lower
    return values[lower] + (values[upper] - values[lower]) * weight


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = []

    for page_size in PAGE_SIZES:
        for version, endpoint in ENDPOINTS.items():
            for run in range(1, RUNS + 1):
                result = request_once(f"{endpoint}?limit={page_size}&offset=0")
                row = {
                    "version": version,
                    "page_size": page_size,
                    "run": run,
                    **result,
                }
                rows.append(row)
                print(
                    f"{version:>5} page={page_size:>3} "
                    f"run={run:02d} sql={result['sql_statements']} "
                    f"latency={result['latency_ms']:.2f} ms"
                )

    summaries = []
    for page_size in PAGE_SIZES:
        for version in ENDPOINTS:
            group = [
                row for row in rows
                if row["page_size"] == page_size
                and row["version"] == version
            ]
            latencies = [row["latency_ms"] for row in group]
            sql_counts = [row["sql_statements"] for row in group]
            summaries.append(
                {
                    "version": version,
                    "page_size": page_size,
                    "requests": len(group),
                    "sql_statements_per_request": round(
                        statistics.mean(sql_counts), 3
                    ),
                    "p50_ms": round(percentile(latencies, 50), 3),
                    "p95_ms": round(percentile(latencies, 95), 3),
                    "p99_ms": round(percentile(latencies, 99), 3),
                }
            )

    output = {
        "seed": 6758,
        "runs_per_case": RUNS,
        "page_sizes": PAGE_SIZES,
        "rows": rows,
        "summaries": summaries,
    }

    output_path = RAW_DIR / "nplus1_results.json"
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(output, file, indent=2)

    print(f"Saved {len(rows)} request measurements to {output_path}")


if __name__ == "__main__":
    main()
