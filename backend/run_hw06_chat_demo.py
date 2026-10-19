"""HW6 Part 2: send a 12-message session to POST /api/chat and save the evidence.

Run from the repository root while the backend is up on port 8458:
    python backend/run_hw06_chat_demo.py
Writes reports/hw06/raw/part2_session.json, part2_memory.json, part2_aggregate.json.
"""
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = "http://127.0.0.1:8458/api"
RAW = Path(__file__).resolve().parents[1] / "reports" / "hw06" / "raw"
USER_ID = "pragya"

MESSAGES = [
    "Hi! I'm Pragya, a grad student at SJSU, and I'm looking for an apartment.",
    "My budget is $2,400 a month including utilities if possible.",
    "I have a cat named Miso, so the place has to be pet friendly.",
    "I want to move in on December 1st because my current lease ends then.",
    "I commute to an internship in Sunnyvale three days a week, so being near Caltrain would help.",
    "I'd prefer a 1-bedroom, but a large studio is fine too.",
    "What should I look for when touring a place with a cat?",
    "Please no ground-floor units, I don't feel safe on the ground floor.",
    "Actually, I just got a raise, so my budget is now $2,700 a month.",
    "In-unit laundry is a must for me.",
    "Can you summarize what you know about my apartment search so far?",
    "What's my cat's name and what's my current budget?",
]


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    session_id = f"demo-{datetime.now():%Y%m%d-%H%M%S}"
    turns = []
    print(f"[{datetime.now().isoformat(timespec='seconds')}] Part 2 demo  user={USER_ID}  session={session_id}")
    for i, message in enumerate(MESSAGES, 1):
        t0 = time.perf_counter()
        res = call("POST", "/chat", {"user_id": USER_ID, "session_id": session_id, "message": message})
        mem, usage = res["memory_used"], res["usage"]
        print(f"\n--- turn {i} ({time.perf_counter() - t0:.1f}s)  prompt={usage['prompt_tokens']} "
              f"completion={usage['completion_tokens']}  window={mem['short_term_count']}  "
              f"facts_retrieved={len(mem['episodic_facts'])}  new_facts={len(mem['new_episodes'])}  "
              f"summary={'yes' if mem['summary_triggered'] else 'no'}  lifetime={'yes' if mem['lifetime_triggered'] else 'no'}")
        print(f"USER: {message}")
        print(f"ASSISTANT: {res['reply']}")
        for f in mem["episodic_facts"]:
            print(f"   retrieved {f['score']:.2f}  {f['fact']}")
        turns.append({"turn": i, "message": message, **res})

    (RAW / "part2_session.json").write_text(json.dumps(turns, indent=2, default=str), encoding="utf-8")
    memory = call("GET", f"/memory/{USER_ID}")
    aggregate = call("GET", f"/aggregate/{USER_ID}")
    (RAW / "part2_memory.json").write_text(json.dumps(memory, indent=2), encoding="utf-8")
    (RAW / "part2_aggregate.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    print(f"\n[{datetime.now().isoformat(timespec='seconds')}] saved part2_session.json, part2_memory.json, part2_aggregate.json")
    print(f"latest session summary:\n{(memory['latest_session_summary'] or {}).get('text')}")
    print(f"latest lifetime summary:\n{(memory['latest_lifetime_summary'] or {}).get('text')}")


if __name__ == "__main__":
    main()
