"""Print the evidence for one HW7 report screenshot (used by take_hw07_screenshots.ps1).

    python code/hw07_screenshot_steps.py 1.1
"""
import json
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
BASE = "http://127.0.0.1:8458"
USERS = {"reader": ("reader1", "Reader#6758"), "writer": ("writer1", "Writer#6758"),
         "moderator": ("moderator1", "Moderator#6758")}


def http(method: str, path: str, body=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else None


def login(role: str) -> str:
    user, pw = USERS[role]
    return http("POST", "/auth/login", {"username": user, "password": pw})[1]["access_token"]


def show(title: str, method: str, path: str, body=None, token_label: str | None = None, token: str | None = None,
         keep=None) -> tuple[int, dict]:
    auth = f"   Authorization: Bearer <{token_label}>" if token_label else ""
    print(f"\n> {method} {path}{auth}" + (f"\n  body: {json.dumps(body)}" if body is not None else ""))
    status, data = http(method, path, body, token)
    shown = data
    if isinstance(data, dict) and keep:
        shown = {k: data[k] for k in keep if k in data}
    elif isinstance(data, list):
        shown = f"[{len(data)} listings] first: " + json.dumps(data[0])[:110]
    print(f"  HTTP {status}  {title}\n  {shown if isinstance(shown, str) else json.dumps(shown)}")
    return status, data


def step_1_1():
    print("Part 1 - POST /auth/login (username + password checked against the hashed MySQL users table)")
    s, d = show("valid login -> JWT", "POST", "/auth/login", {"username": "writer1", "password": "Writer#6758"})
    print(f"  token parts: header.payload.signature = {len(d['access_token'].split('.'))} parts, {len(d['access_token'])} chars")
    show("wrong password", "POST", "/auth/login", {"username": "writer1", "password": "not-the-password"})
    show("unknown user", "POST", "/auth/login", {"username": "nobody", "password": "whatever"})


def step_1_2():
    print("Part 1 - GET /auth/me without a token")
    show("no Authorization header", "GET", "/auth/me")
    print("\nand with a valid token, for comparison:")
    show("valid reader token", "GET", "/auth/me", token_label="reader token", token=login("reader"))


def step_1_2b():
    sys.path.insert(0, str(ROOT / "backend"))
    from dotenv import load_dotenv

    load_dotenv(ROOT / "backend" / ".env")
    from app.auth_jwt import create_access_token

    print("Part 1 - GET /auth/me with an invalid or expired token")
    good = login("reader")
    tampered = good[:-4] + ("AAAA" if not good.endswith("AAAA") else "BBBB")
    expired = create_access_token("reader1", "reader", minutes=-5)
    show("garbage token", "GET", "/auth/me", token_label="abc.def.ghi", token="abc.def.ghi")
    show("tampered signature", "GET", "/auth/me", token_label="reader token with last 4 chars changed", token=tampered)
    show("expired 5 minutes ago", "GET", "/auth/me", token_label="expired reader token", token=expired)


BODY = {"property_address": "77 HW7 Demo Ave, San Jose, CA", "monthly_rent": "2600",
        "submitter_email": "writer1@example.com", "listing_description": "Created during the HW7 role demo",
        "property_category": "Apartment"}


def step_1_3():
    print("Part 1 - POST /listings (create) needs writer or moderator")
    show("reader may not create", "POST", "/listings", BODY, "reader token", login("reader"))
    s, d = show("writer creates", "POST", "/listings", BODY, "writer token", login("writer"),
                keep=["id", "property_address", "monthly_rent", "property_category"])
    (ROOT / "reports" / "hw07" / "raw" / "_demo_listing_id.txt").write_text(str(d["id"]), encoding="utf-8")


def step_1_4():
    lid = int((ROOT / "reports" / "hw07" / "raw" / "_demo_listing_id.txt").read_text(encoding="utf-8"))
    print(f"Part 1 - DELETE /listings/{lid} needs moderator")
    show("writer may not delete", "DELETE", f"/listings/{lid}", None, "writer token", login("writer"))
    show("moderator deletes", "DELETE", f"/listings/{lid}", None, "moderator token", login("moderator"),
         keep=["id", "property_address"])
    show("gone afterwards", "GET", f"/listings/{lid}", None, "reader token", login("reader"))
    (ROOT / "reports" / "hw07" / "raw" / "_demo_listing_id.txt").unlink()


def step_1_5():
    print("Part 1 - GET /listings (list/read) with any valid token")
    _, rows = show("reader lists", "GET", "/listings", None, "reader token", login("reader"))
    show("reader reads one", "GET", f"/listings/{rows[0]['id']}", None, "reader token", login("reader"),
         keep=["id", "property_address", "monthly_rent", "property_category"])
    show("no token", "GET", "/listings")


def _agent_task(case_id: str) -> None:
    sys.path.insert(0, str(ROOT / "backend"))
    sys.path.insert(0, str(ROOT))
    from agent_hw07 import MODEL, TEMPERATURE, run_agent
    from reflexion_hw07 import verify

    cases = json.loads((ROOT / "reports" / "hw07" / "cases" / "agent_tasks.json").read_text(encoding="utf-8"))
    case = next((c for c in cases["cases"] if c["id"] == case_id), cases["error_case"])
    print(f"Part 2 - hand-written agent loop (run_agent, {MODEL}, temperature {TEMPERATURE}) - task {case['id']}: {case['title']}")
    print(f"> run_agent({case['prompt']!r})")
    print()
    r = run_agent(case["prompt"], required_tools=case["required_tools"])
    print()
    print(textwrap.fill(r["final"], 110, initial_indent="FINAL ANSWER: ", subsequent_indent="              "))
    if case_id != "E":
        v = verify(case, r)
        print(f"verifier: {'PASS' if v['passed'] else 'FAIL'} {[p['assertion'] for p in v['problems']]}")
    else:
        crash = "no" if r["stop_reason"] in ("completed", "repair_failed") else "check"
        print(f"crashed: {crash} | execute_tool message: {json.loads(r['trace'][0]['result'])['error'] if r['trace'] else '-'}")


def step_2_a():
    _agent_task("A")


def step_2_b():
    _agent_task("B")


def step_2_c():
    _agent_task("C")


def step_2_e():
    _agent_task("E")


def step_6_1():
    run_py("backend/run_hw07_file_tools.py")


def run_py(script: str, *args: str) -> None:
    subprocess.run([PY, "-u", str(ROOT / script), *args], cwd=ROOT, check=False)


STEPS = {"1.1": step_1_1, "1.2": step_1_2, "1.2b": step_1_2b, "1.3": step_1_3, "1.4": step_1_4, "1.5": step_1_5,
         "2.A": step_2_a, "2.B": step_2_b, "2.C": step_2_c, "2.E": step_2_e, "6.1": step_6_1}

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
    STEPS[sys.argv[1]]()
