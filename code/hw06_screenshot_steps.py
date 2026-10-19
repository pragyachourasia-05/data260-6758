"""Print the evidence for one HW6 report screenshot (used by take_hw06_screenshots.ps1).

    python code/hw06_screenshot_steps.py 1.1
Long values are shortened so each step fits on one screen; the full JSON
is saved under reports/hw06/raw/.
"""
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
BASE = "http://127.0.0.1:8458"
MEM = ROOT / "reports" / "hw06" / "memory"


def http(method: str, path: str, body=None, content_type: str = "application/json"):
    data = body.encode() if isinstance(body, str) else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else None


def show(label: str, method: str, path: str, body=None, content_type="application/json"):
    print(f"\n> {method} {path}" + (f"   body: {body if isinstance(body, str) else json.dumps(body)}" if body is not None else ""))
    status, data = http(method, path, body, content_type)
    print(f"  HTTP {status}  {label}")
    return status, data


def short(value, n=90):
    if isinstance(value, str):
        return value if len(value) <= n else value[:n] + "..."
    if isinstance(value, list):
        return [short(v, n) for v in value]
    if isinstance(value, dict):
        return {k: short(v, n) for k, v in value.items()}
    return value


def mongosh(js: str) -> None:
    subprocess.run(["docker", "exec", "s6758_mongo", "mongosh", "--quiet", "s6758_doc", "--eval", js], check=False)


def step_1_1():
    print("Part 1 - CRUD on MongoDB s6758_doc.listings through FastAPI (port 8458)")
    body = {"title": "1BR in Japantown", "property_type": "apartment", "monthly_rent": 2400,
            "available_from": "2026-11-10T00:00:00Z"}
    s, c = http("POST", "/api/listings", body)
    lid = c["id"]
    print(f"\n> POST /api/listings\n  body: {json.dumps(body)}")
    print(f"  HTTP {s}  id={lid}  status={c['status']} (default)  created_at={c['created_at']}")
    s, items = http("GET", "/api/listings")
    print(f"> GET /api/listings\n  HTTP {s}  {len(items)} listings:")
    for it in items:
        print(f"    {it['id']}  {it['title']:<34} {it['status']:<9} {it['property_type']:<9} ${it['monthly_rent']:,.0f}")
    s, one = http("GET", f"/api/listings/{lid}")
    print(f"> GET /api/listings/{lid}\n  HTTP {s}  title={one['title']!r}  status={one['status']}  rent={one['monthly_rent']:.0f}")
    s, u = http("PUT", f"/api/listings/{lid}", {"status": "pending", "monthly_rent": 2350})
    print(f"> PUT /api/listings/{lid}  {{\"status\": \"pending\", \"monthly_rent\": 2350}}")
    print(f"  HTTP {s}  status={u['status']}  rent={u['monthly_rent']:.0f}  updated_at {c['updated_at'][11:23]} -> {u['updated_at'][11:23]}")
    s, _ = http("DELETE", f"/api/listings/{lid}")
    print(f"> DELETE /api/listings/{lid}\n  HTTP {s}  (no content)")
    s, g = http("GET", f"/api/listings/{lid}")
    print(f"> GET /api/listings/{lid}\n  HTTP {s}  {g['detail']}")


def step_1_2():
    print("Part 1 - validation and error handling (POST/PUT /api/listings)\n")
    cases = [
        ("POST", "/api/listings", {"property_type": "apartment", "available_from": "2026-11-01"}),
        ("POST", "/api/listings", {"title": "x", "property_type": "castle", "available_from": "2026-11-01"}),
        ("POST", "/api/listings", {"title": "x", "property_type": "condo", "available_from": "next week", "monthly_rent": "cheap"}),
        ("POST", "/api/listings", {"title": "x" * 101, "property_type": "condo", "available_from": "2026-11-01"}),
        ("PUT", "/api/listings/65f000000000000000000000", {"status": "sold"}),
    ]
    for method, path, body in cases:
        status, data = http(method, path, body)
        shown = {**body, "title": "<101 x's>"} if len(body.get("title", "")) > 100 else body
        print(f"> {method} {path}  {json.dumps(shown)}")
        errs = "; ".join(f"{err['loc'][-1]}: {err['msg']}" for err in data["detail"])
        print(f"  HTTP {status}  {errs[:104]}")
    status, data = http("POST", "/api/listings", "title=x", "text/plain")
    print(f"> POST /api/listings  Content-Type: text/plain  body: title=x\n  HTTP {status}  {data['detail']}")
    for path in ("/api/listings/123", "/api/listings/65f000000000000000000000"):
        status, data = http("GET", path)
        print(f"> GET {path}\n  HTTP {status}  {data['detail']}")


def step_1_3():
    print("Part 1 - mongo shell: database s6758_doc, collection listings (sample data + validator)\n")
    mongosh(
        'print("> db.listings.find({}, {title:1, status:1, property_type:1, monthly_rent:1, available_from:1, created_at:1})");'
        'db.listings.find({}, {title:1, status:1, property_type:1, monthly_rent:1, available_from:1, created_at:1})'
        '.forEach(d => print(EJSON.stringify(d, {relaxed: true})));'
        'print("\\n> validator required fields / enums:");'
        'const s = db.getCollectionInfos({name:"listings"})[0].options.validator.$jsonSchema;'
        'print("required:", JSON.stringify(s.required));'
        'print("status enum:", JSON.stringify(s.properties.status.enum), " property_type enum:", JSON.stringify(s.properties.property_type.enum));'
        'print("title:", JSON.stringify(s.properties.title));'
    )


def step_2_2():
    print("Part 2 - GET /api/memory/pragya  (message text shortened to fit; full JSON in reports/hw06/raw/part2_memory.json)\n")
    status, data = http("GET", "/api/memory/pragya")
    data["recent_messages"] = [f"[{m['role']}] {m['content']}" for m in data["recent_messages"]]
    facts = data["episodic_facts"]
    data["episodic_facts"] = [f"({f['importance']:.1f}) {f['fact']}" for f in facts[:10]] + [f"... {len(facts) - 10} more"]
    for key in ("latest_session_summary", "latest_lifetime_summary"):
        if data.get(key):
            data[key] = {"scope": data[key]["scope"], "session_id": data[key]["session_id"], "text": data[key]["text"]}
    print(f"HTTP {status}")
    print(json.dumps(short(data, 95), indent=1))


def step_2_3():
    print("Part 2 - GET /api/aggregate/pragya\n")
    status, data = http("GET", "/api/aggregate/pragya")
    for s in data["recent_summaries"]:
        s.pop("user_id", None)
        s["text"] = s["text"].replace("\n", " | ")
    print(f"HTTP {status}")
    print(json.dumps(short(data, 150), indent=1))


def step_2_4():
    print("Part 2 - mongo shell: messages, summaries and episodes (database s6758_doc)\n")
    mongosh(
        'const cut = (s, n) => s.length > n ? s.slice(0, n) + "..." : s;'
        'const one = (s) => s.split(String.fromCharCode(10)).join(" | ");'
        'print("> show collections:", db.getCollectionNames().sort().join(", "));'
        'for (const c of ["messages","summaries","episodes"]) print(`  ${c}: ${db[c].countDocuments()} documents, ${db[c].countDocuments({user_id:"pragya"})} for user pragya`);'
        'print("> db.messages.find({user_id: \\"pragya\\"}).sort({created_at: 1}).limit(2)");'
        'db.messages.find({user_id:"pragya"}).sort({created_at:1}).limit(2).forEach(d => print(`  {user_id: "${d.user_id}", session_id: "${d.session_id}", role: "${d.role}",`, `\n   content: "${cut(d.content, 60)}", created_at: ${d.created_at.toISOString().slice(0, 19)}}`));'
        'print("> db.summaries.findOne({user_id: \\"pragya\\", scope: ...})  latest session and lifetime summary");'
        'for (const sc of ["session","user"]) { const d = db.summaries.findOne({user_id:"pragya", scope:sc}, {}, {sort:{created_at:-1}}); print(`  {scope: "${d.scope}", session_id: ${d.session_id ? "\\"" + d.session_id + "\\"" : null},`, `\n   text: "${cut(one(d.text), 90)}"}`); }'
        'print("> db.episodes.findOne({user_id: \\"pragya\\", fact: /Miso/})");'
        'const e = db.episodes.findOne({user_id:"pragya", fact:/Miso/}) || db.episodes.findOne({user_id:"pragya"});'
        'print(`  {fact: "${e.fact}", importance: ${e.importance}, session_id: "${e.session_id}",`, `\n   embedding: ${e.embedding.length} floats (${e.embedding.filter(x => x !== 0).length} non-zero, e.g. ${e.embedding.filter(x => x !== 0).slice(0,3).map(x => x.toFixed(4)).join(", ")}), created_at: ${e.created_at.toISOString().slice(0, 19)}}`);'
    )


def run_client(session_file: Path):
    with session_file.open("rb") as fh:
        subprocess.run([PY, str(ROOT / "code" / "hw1_client.py")], stdin=fh, cwd=ROOT, check=False)


def step_4_1():
    print("Part 4 - HW1 client with AGENT.md + MEMORY.md: startup check and /help\n")
    print("> python code/hw1_client.py   then: /help\n")
    p = subprocess.run([PY, str(ROOT / "code" / "hw1_client.py")], input="/help\n/quit\n",
                       text=True, capture_output=True, cwd=ROOT)
    print(p.stdout.split("Final cumulative stats")[0].rstrip())


def step_4_1b():
    print("Part 4 - /memory  (file body shortened to fit the window; full file: MEMORY.md)\n")
    p = subprocess.run([PY, str(ROOT / "code" / "hw1_client.py")], input="/memory\n/quit\n",
                       text=True, capture_output=True, cwd=ROOT)
    out = p.stdout.split("You: ", 1)[1].split("Final cumulative stats")[0].rstrip().splitlines()
    status = [l for l in out if l.startswith("[")]
    body = [l for l in out if not l.startswith("[") and l.strip() and l.strip() != "You:"]
    print("You: /memory")
    for l in body[:14]:
        print(l[:116])
    print(f"... ({len(body) - 14} more lines, incl. Resolved contradictions)")
    print("\n".join(status))


def step_4_2():
    print("Part 4 - /compact on the 55-line test MEMORY.md (memory/MEMORY_original.md)\n")
    live = ROOT / "MEMORY.md"
    backup = live.read_text(encoding="utf-8")
    shutil.copy(MEM / "MEMORY_original.md", live)
    try:
        print(f"> wc -l MEMORY.md  ->  {len(live.read_text(encoding='utf-8').splitlines())} lines")
        print("> python code/hw1_client.py < reports/hw06/cases/part4_session_a.txt\n")
        run_client(ROOT / "reports" / "hw06" / "cases" / "part4_session_a.txt")
        print(f"\n> wc -l MEMORY.md  ->  {len(live.read_text(encoding='utf-8').splitlines())} lines")
    finally:
        live.write_text(backup, encoding="utf-8")  # keep the reviewed MEMORY.md in the repo


def step_4_3():
    print("Part 4 - generated function checked against AGENT.md\n")
    print("> python code/check_agent_md_rules.py   (model output as generated, saved in raw/agent_md_generated_v1/)")
    v1 = json.loads((ROOT / "reports/hw06/raw/agent_md_generated_v1/agent_md_check.json").read_text(encoding="utf-8"))
    for c in v1["checks"]:
        print(f"{'PASS' if c['passed'] else 'FAIL'}  {c['rule']}  ({c['detail']})")
    print(f"SUMMARY: {sum(c['passed'] for c in v1['checks'])}/{len(v1['checks'])}\n")
    print("> python code/check_agent_md_rules.py   (after correction: src/generated/rent_parser.py)")
    subprocess.run([PY, str(ROOT / "code" / "check_agent_md_rules.py")], cwd=ROOT, check=False)


STEPS = {"1.1": step_1_1, "1.2": step_1_2, "1.3": step_1_3, "2.2": step_2_2, "2.3": step_2_3,
         "2.4": step_2_4, "4.1": step_4_1, "4.1b": step_4_1b, "4.2": step_4_2, "4.3": step_4_3}

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
    STEPS[sys.argv[1]]()
