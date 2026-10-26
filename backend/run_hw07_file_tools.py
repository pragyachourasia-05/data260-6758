"""HW7 Part 6: one combined test run for the file tools and the bash safety gate.

    python backend/run_hw07_file_tools.py
(a) integration: 3 small Python files in a temporary sandbox; ONE instruction makes the agent
    go glob -> search -> read to find the file containing DEBUG and show it
(b) safety gate: 5 commands that must pass, 5 that must be blocked, plus the false allows found
    in gate v1 and fixed in v2
Writes reports/hw07/raw/part6_safety_gate_results.json and part6_integration_trace.json.
"""
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from agent_hw07 import run_agent  # noqa: E402

from app import file_tools as ft  # noqa: E402

RAW = HERE.parent / "reports" / "hw07" / "raw"

FILE_TOOLS = [
    {"type": "function", "function": {"name": "glob_files", "description": "List files in the sandbox matching a glob pattern, e.g. *.py",
                                      "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "search_in_files", "description": "Search inside files. Call it as search_in_files(pattern=\"TEXT\", file_pattern=\"*.py\"); "
                                      "pattern is the text or regex to find (required).",
                                      "parameters": {"type": "object", "properties": {
                                          "pattern": {"type": "string", "description": "Text or regex to find, e.g. DEBUG"},
                                          "file_pattern": {"type": "string", "description": "Which files to search, e.g. *.py"}},
                                                     "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a sandbox file; max_lines limits the output",
                                      "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "max_lines": {"type": "integer"}},
                                                     "required": ["path"]}}},
]
FILES = {
    "billing.py": 'def monthly_total(rides, rate):\n    """Sum of per-ride charges."""\n    return sum(rate * r for r in rides)\n',
    "routes.py": 'ROUTES = ["/listings", "/auth/login"]\n\n\ndef has_route(path):\n    return path in ROUTES\n',
    "settings.py": 'DEBUG = True  # turn off before deploying\nLOG_LEVEL = "info"\nMAX_RIDES = 500\n',
}
PASS = ["ls -la", "echo hello", "python --version", "git status", "cat billing.py | grep rate"]
BLOCK = ["rm -rf build", "sudo apt install curl", "chmod -R 777 .", "dd if=/dev/zero of=/dev/sda bs=1M", "echo pwned > /etc/hosts"]


def execute(name: str, args: dict) -> str:
    fn = {"glob_files": ft.glob_files, "search_in_files": ft.search_in_files, "read_file": ft.read_file}[name]
    return json.dumps(fn(**args))


def main() -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] HW7 Part 6 - file tools + safety gate")
    sandbox = ft.set_sandbox(Path(tempfile.mkdtemp(prefix="data260_hw7_sandbox_")))
    print(f"sandbox: {sandbox}")
    for name, body in FILES.items():
        ft.write_file(name, body)
    print("created:", ", ".join(FILES))

    print("\n(a) integration test - one instruction: glob -> search -> read")
    instruction = ("Find the Python file in the sandbox that contains DEBUG and show its contents. "
                   "First list the .py files with glob_files, then call search_in_files with pattern \"DEBUG\", then read_file the path that search_in_files returned.")
    print(f"instruction: {instruction}")
    for attempt in range(1, 4):  # the small model's tool order varies, so allow up to 3 attempts
        print(f"attempt {attempt}:")
        run = run_agent(instruction, required_tools=["glob_files", "search_in_files", "read_file"], tools=FILE_TOOLS,
                        max_repairs=3,  # three-step chain: one more bounded repair than the domain tasks
                        execute=execute, system_prompt="You are a coding assistant with sandboxed file tools. Use them "
                        "one at a time, in the order the user gives, and finish with the file name and its contents.")
        found = [t for t in run["trace"] if t["tool"] == "read_file" and "DEBUG" in t["result"]]
        order = [t["tool"] for t in run["trace"] if t["ok_call"]]
        steps = iter(order)  # glob, search and read must all run, in that order (other calls may sit between)
        in_order = all(any(tool == want for tool in steps) for want in ("glob_files", "search_in_files", "read_file"))
        integration_ok = bool(found) and in_order
        if integration_ok:
            break
    print(f"agent answer (attempt {attempt}): {run['final'][:300]}")
    print(f"integration result: {'PASS' if integration_ok else 'FAIL'} (calls in order: {' -> '.join(order)}; "
          f"read_file returned the file containing DEBUG: {bool(found)})")

    print("\nother tool checks")
    print("  read_file(max_lines=1):", json.dumps(ft.read_file("settings.py", max_lines=1)["data"]))
    print("  edit_file diff:\n    " + ft.edit_file("settings.py", "DEBUG = True", "DEBUG = False")["data"]["diff"].replace("\n", "\n    "))
    print("  path escape:", ft.read_file("../outside.txt")["error"])

    print("\n(b) safety gate - is_destructive / confirm_bash (pure Python, no model)")
    rows = []
    for cmd, expect in [(c, True) for c in PASS] + [(c, False) for c in BLOCK]:
        gate = ft.confirm_bash(cmd)
        ok = gate["allowed"] == expect
        rows.append({"command": cmd, "expected": "allow" if expect else "block", "is_destructive": ft.is_destructive(cmd),
                     **gate, "correct": ok})
        print(f"  {'PASS' if ok else 'FAIL'}  expect {'allow' if expect else 'block':5}  got {'allow' if gate['allowed'] else 'block':5}  "
              f"destructive={str(ft.is_destructive(cmd)):5}  {cmd:38}  {gate['reason']}")
    before = json.loads((RAW / "part6_false_allows_before_fix.json").read_text(encoding="utf-8"))
    print("\n  false allows found in gate v1 and their result with the fixed gate v2:")
    fixed = []
    for f in before["false_allows"]:
        now = ft.confirm_bash(f["command"])
        fixed.append({"command": f["command"], "v1": "allow", "v2": "allow" if now["allowed"] else "block", "v2_reason": now["reason"]})
        print(f"    v1 allow -> v2 {'allow' if now['allowed'] else 'block'}  {f['command']:45}  {now['reason']}")
    print(f"  confirmed destructive: {ft.confirm_bash('rm -rf build', auto_approve=True)}")
    score = sum(r["correct"] for r in rows)
    print(f"\nSUMMARY: integration {'PASS' if integration_ok else 'FAIL'} | safety gate {score}/10 correct | "
          f"false allows fixed {sum(f['v2'] == 'block' for f in fixed)}/{len(fixed)}")

    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part6_safety_gate_results.json").write_text(json.dumps(
        {"when": datetime.now().isoformat(timespec="seconds"), "safe_prefixes": list(ft.SAFE_PREFIXES), "tests": rows,
         "correct": score, "false_allows_fixed": fixed}, indent=2), encoding="utf-8")
    (RAW / "part6_integration_trace.json").write_text(json.dumps(
        {"instruction": instruction, "pass": integration_ok, **{k: run[k] for k in ("final", "trace", "stop_reason", "tool_calls")}},
        indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
