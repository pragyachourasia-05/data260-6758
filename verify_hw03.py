import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HW3 = ROOT / "reports" / "hw03"

required_files = [
    ROOT / "main.py",
    ROOT / "routers" / "auth.py",
    ROOT / "templates" / "index.html",
    ROOT / "templates" / "login.html",
    ROOT / "templates" / "dashboard.html",
    ROOT / "rag" / "retrieval_compare.py",
    HW3 / "questions.yaml",
    HW3 / "METRICS.md",
    HW3 / "AI_USE.md",
    HW3 / "SOURCES.md",
    HW3 / "CORPUS_MANIFEST.json",
    HW3 / "report.pdf",
    HW3 / "raw" / "retrieval_results.json",
    HW3 / "raw" / "retrieval_summary.json",
]

checks = []

missing = [str(p.relative_to(ROOT)) for p in required_files if not p.exists()]
checks.append({
    "name": "required_hw03_files",
    "passed": len(missing) == 0,
    "detail": "All required files exist." if not missing else f"Missing: {missing}",
})

try:
    results = json.loads(
        (HW3 / "raw" / "retrieval_results.json").read_text(encoding="utf-8")
    )
    count = len(results.get("results", []))
    checks.append({
        "name": "retrieval_results",
        "passed": count == 15,
        "detail": f"Found {count} results; expected 15.",
    })
except Exception as exc:
    checks.append({
        "name": "retrieval_results",
        "passed": False,
        "detail": str(exc),
    })

try:
    summary = json.loads(
        (HW3 / "raw" / "retrieval_summary.json").read_text(encoding="utf-8")
    )
    count = len(summary.get("summaries", []))
    checks.append({
        "name": "retrieval_summary",
        "passed": count == 3,
        "detail": f"Found {count} techniques; expected 3.",
    })
except Exception as exc:
    checks.append({
        "name": "retrieval_summary",
        "passed": False,
        "detail": str(exc),
    })

try:
    commit_hash = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True
    ).strip()
except Exception:
    commit_hash = "unknown"

output = {
    "homework": "HW3",
    "sid4": "6758",
    "domain": "Rental housing listings",
    "commit_hash": commit_hash,
    "checks": checks,
    "passed": all(item["passed"] for item in checks),
}

(HW3 / "verification.json").write_text(
    json.dumps(output, indent=2),
    encoding="utf-8"
)

print(json.dumps(output, indent=2))