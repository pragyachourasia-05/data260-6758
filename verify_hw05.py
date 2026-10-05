"""Objective smoke checks; run from the repository root."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports" / "hw05"


def check(name, fn):
    try:
        fn()
        return {"name": name, "passed": True, "detail": "ok"}
    except Exception as exc:
        return {"name": name, "passed": False, "detail": str(exc)}


def main():
    checks = []
    checks.append(check("hw05_directories", lambda: [(_ for _ in ()).throw(FileNotFoundError(str(p))) for p in [REPORTS, REPORTS / "raw"] if not p.exists()]))
    checks.append(check("offline_tool_tests", lambda: subprocess.run([sys.executable, str(ROOT / "backend" / "offline_tests.py")], cwd=ROOT, check=True, capture_output=True, text=True)))
    checks.append(check("fault_records", lambda: (_ for _ in ()).throw(AssertionError("expected 150 rows")) if len(json.loads((REPORTS / "raw" / "fault_injection_results.json").read_text(encoding="utf-8")).get("rows", [])) != 150 else None))
    checks.append(check("mcp_source_files", lambda: [(_ for _ in ()).throw(FileNotFoundError(str(p))) for p in [ROOT / "backend" / "app" / "meals_server.py", ROOT / "backend" / "app" / "domain_mcp_server.py"] if not p.exists()]))
    result = {"homework": "HW5", "sid4": "6758", "seed": 6758, "verify_seed": 266758, "checks": checks, "passed": all(c["passed"] for c in checks)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
