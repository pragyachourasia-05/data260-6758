import json
import subprocess
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports" / "hw04"
RAW = REPORTS / "raw"


def check(name, passed, detail):
    return {"name": name, "passed": bool(passed), "detail": detail}


def http_check(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status == 200, response.read().decode(errors="replace")
    except Exception as exc:
        return False, str(exc)


def main():
    checks = []
    required = [
        REPORTS / "AI_USE.md",
        REPORTS / "RUN_LOG.txt",
        REPORTS / "METRICS.md",
        REPORTS / "cases" / "rag_questions.json",
        REPORTS / "raw" / "nplus1_results.json",
        REPORTS / "raw" / "retrieved_chunks.json",
        REPORTS / "raw" / "rag_comparison.json",
        REPORTS / "raw" / "rag_k_sweep.json",
        REPORTS / "raw" / "rag_evaluation.json",
        ROOT / "backend" / "seed_hw04.py",
        ROOT / "backend" / "benchmark_nplus1.py",
        ROOT / "backend" / "app" / "nplus1.py",
        ROOT / "rag" / "rag.py",
    ]
    checks.append(check("required_files", all(path.exists() for path in required), "All required HW4 files exist."))

    corpus = list((REPORTS / "corpus").glob("*.md"))
    checks.append(check("corpus_documents", len(corpus) >= 5, f"Found {len(corpus)} corpus documents; expected at least 5."))

    questions_path = REPORTS / "cases" / "rag_questions.json"
    try:
        questions = json.loads(questions_path.read_text(encoding="utf-8"))["questions"]
        checks.append(check("rag_questions", len(questions) == 6, f"Found {len(questions)} RAG questions; expected 6."))
    except Exception as exc:
        checks.append(check("rag_questions", False, str(exc)))

    try:
        benchmark = json.loads((RAW / "nplus1_results.json").read_text(encoding="utf-8"))
        rows = benchmark["rows"]
        patterns = sorted({(r["version"], r["page_size"], r["sql_statements"]) for r in rows})
        expected = sorted([
            ("naive", 10, 11), ("naive", 50, 51), ("naive", 200, 201),
            ("fixed", 10, 1), ("fixed", 50, 1), ("fixed", 200, 1),
        ])
        checks.append(check("nplus1_measurements", len(rows) == 180, f"Found {len(rows)} measurements; expected 180."))
        checks.append(check("nplus1_sql_patterns", patterns == expected, f"Observed SQL patterns: {patterns}"))
    except Exception as exc:
        checks.append(check("nplus1_measurements", False, str(exc)))

    rag_outputs = [RAW / name for name in ["retrieved_chunks.json", "rag_comparison.json", "rag_k_sweep.json", "rag_evaluation.json", "rag_analysis.txt"]]
    checks.append(check("rag_outputs", all(path.exists() for path in rag_outputs), "All required RAG output files exist."))

    ok_health, health_detail = http_check("http://localhost:8458/health")
    checks.append(check("backend_health", ok_health, health_detail[:200]))

    ok_naive, naive_detail = http_check("http://localhost:8458/bench/listings-naive?limit=10")
    checks.append(check("naive_endpoint", ok_naive, "Naive benchmark endpoint responded." if ok_naive else naive_detail[:200]))

    ok_fixed, fixed_detail = http_check("http://localhost:8458/bench/listings-fixed?limit=10")
    checks.append(check("fixed_endpoint", ok_fixed, "Fixed benchmark endpoint responded." if ok_fixed else fixed_detail[:200]))

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = "unknown"

    output = {
        "homework": "HW4",
        "sid4": "6758",
        "domain": "Rental housing listings",
        "seed": 6758,
        "verify_seed": 266758,
        "commit_hash": commit,
        "checks": checks,
        "passed": all(item["passed"] for item in checks),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "verification.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
