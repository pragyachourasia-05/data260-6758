import json
import py_compile
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
HW2 = ROOT / "reports" / "hw02"

checks = []


def add_check(name, passed, detail):
    checks.append({
        "name": name,
        "passed": bool(passed),
        "detail": detail,
    })


def git_hash():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unavailable"


# Required files
required_files = [
    HW2 / "METRICS.md",
    HW2 / "AI_USE.md",
    HW2 / "RUN_LOG.txt",
    HW2 / "cases" / "schema_input.json",
    HW2 / "cases" / "adversarial_input.json",
    HW2 / "raw" / "schema_validation_results.json",
    HW2 / "raw" / "ceiling2_results.json",
    HW2 / "raw" / "ceiling10_results.json",
    HW2 / "raw" / "adversarial_results.json",
]

missing = [str(path.relative_to(ROOT)) for path in required_files if not path.exists()]
add_check(
    "required_hw02_files",
    not missing,
    "All required files exist." if not missing else f"Missing: {missing}",
)

# Raw experiment counts
try:
    schema_runs = json.loads(
        (HW2 / "raw" / "schema_validation_results.json").read_text(encoding="utf-8")
    )["runs"]
    add_check(
        "schema_validation_runs",
        len(schema_runs) == 30,
        f"Found {len(schema_runs)} runs; expected 30.",
    )
except Exception as exc:
    add_check("schema_validation_runs", False, str(exc))

try:
    ceiling2_runs = json.loads(
        (HW2 / "raw" / "ceiling2_results.json").read_text(encoding="utf-8")
    )["runs"]
    add_check(
        "ceiling_2_runs",
        len(ceiling2_runs) == 20,
        f"Found {len(ceiling2_runs)} runs; expected 20.",
    )
except Exception as exc:
    add_check("ceiling_2_runs", False, str(exc))

try:
    ceiling10_runs = json.loads(
        (HW2 / "raw" / "ceiling10_results.json").read_text(encoding="utf-8")
    )["runs"]
    add_check(
        "ceiling_10_runs",
        len(ceiling10_runs) == 20,
        f"Found {len(ceiling10_runs)} runs; expected 20.",
    )
except Exception as exc:
    add_check("ceiling_10_runs", False, str(exc))

try:
    adversarial_runs = json.loads(
        (HW2 / "raw" / "adversarial_results.json").read_text(encoding="utf-8")
    )["runs"]
    add_check(
        "adversarial_runs",
        len(adversarial_runs) == 5,
        f"Found {len(adversarial_runs)} runs; expected 5.",
    )
except Exception as exc:
    add_check("adversarial_runs", False, str(exc))

# Compile the graph and API code without running the model
try:
    for filename in ["graph_demo.py", "workflow.py", "router.py", "nodes.py", "state.py", "schemas.py", "main.py"]:
        py_compile.compile(str(ROOT / filename), doraise=True)
    add_check("python_compile", True, "Graph and FastAPI files compile successfully.")
except Exception as exc:
    add_check("python_compile", False, str(exc))

verification = {
    "homework": "HW2",
    "sid4": "6758",
    "domain": "Rental housing listings",
    "model": "llama3.2:3b",
    "temperature": 0.0,
    "seed": 6758,
    "verify_seed": 266758,
    "commit_hash": git_hash(),
    "checks": checks,
    "passed": all(check["passed"] for check in checks),
}

output_path = HW2 / "verification.json"
output_path.write_text(json.dumps(verification, indent=2), encoding="utf-8")
print(json.dumps(verification, indent=2))