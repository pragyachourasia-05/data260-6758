"""HW6 Part 4.4: check a module + its tests against the rules in AGENT.md.

    python code/check_agent_md_rules.py [module.py] [test_file.py]

Defaults to the generated src/generated/rent_parser.py and tests/test_rent_parser.py.
Each check names the AGENT.md rule it enforces. Results go to
reports/hw06/raw/agent_md_check.json; exit code 1 if any check fails.
"""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAKE = re.compile(r"^_?[a-z][a-z0-9_]*$")
SECRET = re.compile(r"""(password|passwd|api_key|apikey|secret|token)\s*=\s*['"][^'"]+['"]""", re.IGNORECASE)
NETWORK_MODULES = {"requests", "httpx", "urllib", "socket", "pymongo", "sqlalchemy", "pymysql", "ollama", "langchain_ollama"}


def functions(tree: ast.AST) -> list[ast.FunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def check_module(path: Path) -> list[dict]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    funcs = [f for f in functions(tree) if not f.name.startswith("_")]
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    imports = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imports |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    raises = [n for n in ast.walk(tree) if isinstance(n, ast.Raise)]

    def unhinted(f):
        args = f.args.posonlyargs + f.args.args + f.args.kwonlyargs
        missing = [a.arg for a in args if a.annotation is None and a.arg not in ("self", "cls")]
        if f.returns is None:
            missing.append("return")
        return missing

    return [
        {"rule": "Coding conventions: snake_case function names",
         "passed": bool(funcs) and all(SNAKE.match(f.name) for f in functions(tree)),
         "detail": ", ".join(f.name for f in functions(tree)) or "no functions found"},
        {"rule": "Coding conventions: type hints on every parameter and return value",
         "passed": bool(funcs) and not any(unhinted(f) for f in funcs),
         "detail": "; ".join(f"{f.name}: missing {unhinted(f)}" for f in funcs if unhinted(f)) or "all annotated"},
        {"rule": "Coding conventions: docstring on every public function",
         "passed": bool(funcs) and all(ast.get_docstring(f) for f in funcs),
         "detail": ", ".join(f.name for f in funcs if not ast.get_docstring(f)) or "all documented"},
        {"rule": "Coding conventions: invalid input raises ValueError",
         "passed": any(isinstance(r.exc, ast.Call) and getattr(r.exc.func, "id", "") == "ValueError" for r in raises),
         "detail": f"{len(raises)} raise statement(s)"},
        {"rule": "Coding conventions: no print() in library code",
         "passed": not any(getattr(c.func, "id", "") == "print" for c in calls),
         "detail": "no print calls" if not any(getattr(c.func, "id", "") == "print" for c in calls) else "print() found"},
        {"rule": "Coding conventions / prohibited: no hard-coded secrets",
         "passed": not SECRET.search(source), "detail": "none found" if not SECRET.search(source) else SECRET.search(source).group(0)},
        {"rule": "Technology stack / testing: no network, database or model imports",
         "passed": not (imports & NETWORK_MODULES), "detail": ", ".join(sorted(imports)) or "no imports"},
    ]


def check_tests(path: Path) -> list[dict]:
    if not path.exists():
        return [{"rule": "Testing approach: test_*.py file exists", "passed": False, "detail": f"{path} missing"}]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tests = [f for f in functions(tree) if f.name.startswith("test_")]
    uses_raises = any(
        isinstance(n, ast.Attribute) and n.attr == "raises" for n in ast.walk(tree)
    ) and "ValueError" in path.read_text(encoding="utf-8")
    run = subprocess.run([sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True)
    last = (run.stdout.strip().splitlines() or [""])[-1]
    return [
        {"rule": "Testing approach: test_*.py file exists", "passed": path.name.startswith("test_"), "detail": path.name},
        {"rule": "Testing approach: at least one normal case and one invalid-input case",
         "passed": len(tests) >= 2 and uses_raises, "detail": f"{len(tests)} tests, pytest.raises(ValueError): {uses_raises}"},
        {"rule": "Testing approach: tests pass offline", "passed": run.returncode == 0, "detail": last},
    ]


def main() -> int:
    module = (Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "src" / "generated" / "rent_parser.py").resolve()
    tests = (Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "tests" / "test_rent_parser.py").resolve()
    results = check_module(module) + check_tests(tests)
    for r in results:
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['rule']}  ({r['detail']})")
    passed = sum(r["passed"] for r in results)
    print(f"SUMMARY: {passed}/{len(results)} AGENT.md checks pass for {module.relative_to(ROOT)}")
    out = ROOT / "reports" / "hw06" / "raw" / "agent_md_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"module": str(module.relative_to(ROOT)), "tests": str(tests.relative_to(ROOT)),
                               "checks": results, "passed": passed == len(results)}, indent=2), encoding="utf-8")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
