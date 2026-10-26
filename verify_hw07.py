"""HW7 smoke checks; run from the repository root with MySQL, Ollama and the backend (port 8458) up.

    python verify_hw07.py        (or: make verify-hw07)

Checks behaviour, not wording, and writes reports/hw07/verification.json. It creates (and deletes) one
temporary listing and a temporary sandbox directory; it never modifies application code.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "reports" / "hw07"
RAW = REPORTS / "raw"
BASE = "http://127.0.0.1:8458"
SID4 = 6758
VERIFY_SEED = 260000 + SID4


def http(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else None


def check(name, fn):
    try:
        return {"name": name, "passed": True, "detail": fn() or "ok"}
    except Exception as exc:  # each check reports its own failure
        return {"name": name, "passed": False, "detail": f"{type(exc).__name__}: {exc}"}


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def token(user, pw):
    s, d = http("POST", "/auth/login", {"username": user, "password": pw})
    expect(s == 200 and d.get("access_token"), f"login {user} -> {s}")
    return d["access_token"]


def login_checks():
    t = token("reader1", "Reader#6758")
    bad = http("POST", "/auth/login", {"username": "reader1", "password": f"wrong-{VERIFY_SEED}"})[0]
    expect(bad == 401, f"invalid login -> {bad}")
    return f"valid -> token ({len(t.split('.'))} JWT parts), invalid -> 401"


def me_checks():
    none = http("GET", "/auth/me")[0]
    garbage = http("GET", "/auth/me", token="abc.def.ghi")[0]
    s, d = http("GET", "/auth/me", token=token("writer1", "Writer#6758"))
    expect(none == 401 and garbage == 401 and s == 200 and d["role"] == "writer", f"{none}/{garbage}/{s}")
    return "no token 401, invalid token 401, valid 200 role=writer"


def rbac_checks():
    body = {"property_address": f"{VERIFY_SEED} Verify St", "monthly_rent": "1", "submitter_email": "verify@example.com",
            "listing_description": "verify_hw07 temporary row", "property_category": "Apartment"}
    r, w, m = token("reader1", "Reader#6758"), token("writer1", "Writer#6758"), token("moderator1", "Moderator#6758")
    codes = [http("GET", "/listings", token=r)[0], http("POST", "/listings", body, r)[0]]
    s, created = http("POST", "/listings", body, w)
    codes.append(s)
    codes += [http("DELETE", f"/listings/{created['id']}", token=w)[0], http("DELETE", f"/listings/{created['id']}", token=m)[0]]
    expect(codes == [200, 403, 201, 403, 200], f"got {codes}")
    return "list reader 200, create reader 403 / writer 201, delete writer 403 / moderator 200"


def agent_loop_check():
    from agent_hw07 import run_agent

    cases = json.loads((REPORTS / "cases" / "agent_tasks.json").read_text(encoding="utf-8"))["cases"]
    r = run_agent(cases[0]["prompt"], required_tools=cases[0]["required_tools"], log=lambda _m: None)
    expect(r["stop_reason"] == "completed" and r["tool_calls"] >= 2, f"stop={r['stop_reason']} calls={r['tool_calls']}")
    return f"task A completed with {r['tool_calls']} tool calls, {r['repairs']} repairs"


def safety_gate_check():
    from app import file_tools as ft

    ft.set_sandbox(Path(tempfile.mkdtemp(prefix="verify_hw07_")))
    allow = ["ls -la", "echo hello", "python --version", "git status", "cat a.py | grep DEBUG"]
    block = ["rm -rf build", "sudo apt install x", "chmod -R 777 .", "dd if=/dev/zero of=/dev/sda", "echo x > /etc/hosts",
             "ls && rm -rf ~", "echo hi && python evil.py"]
    wrong = [c for c in allow if not ft.confirm_bash(c)["allowed"]] + [c for c in block if ft.confirm_bash(c)["allowed"]]
    expect(not wrong, f"wrong decisions: {wrong}")
    ft.write_file("a.py", "DEBUG = True\n")
    expect(ft.search_in_files("DEBUG", "*.py")["data"]["matches"][0]["path"] == "a.py", "search_in_files")
    return f"{len(allow)} allowed, {len(block)} blocked, file tools work in a temp sandbox"


def mrkl_tool_check():
    from app import bikeshare_tools as bt

    csv = REPORTS / "cases" / "bikeshare" / "scenario_payperuse.csv"
    expect(bt.csv_sql("SELECT COUNT(*) AS n FROM trips", csv)["data"]["rows"][0]["n"] >= 500, "row count")
    expect(not bt.csv_sql("DELETE FROM trips", csv)["success"], "DELETE was not rejected")
    expect(not bt.csv_sql("SELECT 1; DROP TABLE trips", csv)["success"], "stacked statement was not rejected")
    expect(bt.calculator("29 * 16 + 39.95")["data"]["value"] == 503.95, "calculator")
    expect(not bt.calculator("__import__('os')")["success"], "calculator accepted code")
    page = REPORTS / "cases" / "bikeshare" / "hostile_override.html"
    expect(bt.policy_retriever(str(page), "month pass price")["data"]["passages"], "retriever returned nothing")
    return "csv_sql read-only contract, calculator whitelist, policy_retriever passages"


def artifacts_check():
    rel = json.loads((RAW / "part2_reliability.json").read_text(encoding="utf-8"))
    comp = json.loads((RAW / "part3_comparison.json").read_text(encoding="utf-8"))
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in (RAW / "part4_runs").glob("*.json")]
    attacks = json.loads((RAW / "part5_attack_results.json").read_text(encoding="utf-8"))
    gate = json.loads((RAW / "part6_safety_gate_results.json").read_text(encoding="utf-8"))
    expect(rel["summary"]["attempts"] >= 20, "fewer than 20 reliability attempts")
    expect({"original", "reflexion"} <= set(comp["summary"]), "comparison summary")
    labels = {r.get("label") for r in runs if r.get("pricing_snapshot", {}).get("sha256")}
    expect({"membership", "payperuse"} <= labels, f"scenario snapshots: {labels}")
    expect(len(attacks) == 9, f"{len(attacks)} attack results")
    expect(gate["correct"] == 10, "gate test")
    return f"reliability {rel['summary']['attempts']} attempts, 2 scenario snapshots, 9 attack runs, gate 10/10"


def main() -> int:
    checks = [check("backend_health_port_8458", lambda: http("GET", "/health")[1]["status"]),
              check("auth_login_token_and_401", login_checks),
              check("auth_me_401_and_200", me_checks),
              check("rbac_200_201_403", rbac_checks),
              check("agent_loop_completes_task_A", agent_loop_check),
              check("safety_gate_and_file_tools", safety_gate_check),
              check("mrkl_tools_contracts", mrkl_tool_check),
              check("raw_artifacts_present", artifacts_check)]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = "unknown"
    result = {"homework": "HW7", "sid4": str(SID4), "commit_hash": commit,
              "model_configuration": {"agent_loop": "llama3.2:3b via src/model_client.ModelClient, temperature 0.7",
                                      "bikeshare_agent": "qwen3:8b via LangChain create_agent, temperature 0, seed 6758",
                                      "jwt": "HS256, 30-minute access tokens"},
              "seed": SID4, "verify_seed": VERIFY_SEED, "checks": checks,
              "passed": all(c["passed"] for c in checks)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
