"""Part 5 offline tests (no Ollama, no network, no database).

Same output format as your Part 4 runner. To merge into offline_tests.py, copy the
two test functions and add them to your list of tests. Run on its own with:
  python backend\\test_part5.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent import MockModel, coerce_args, run_agent  # noqa: E402

STUDENT = "Pragya Chourasia"


def fake_execute_ok(name, inputs):
    return json.dumps({"ok": True, "data": {"echo": name}, "error": None})


def fake_execute_blocked(name, inputs):
    return json.dumps({"ok": False, "data": None,
                       "error": "blocked by safety rule: private owner data is not returned"})


def test_execute_tool_blocks_safety_violation():
    """Uses your real execute_tool: include_private=True must be blocked by the safety rule."""
    from agent import load_execute_tool
    execute = load_execute_tool()
    out = json.loads(execute("listing_summary", {"category": "Apartment", "include_private": True}))
    assert out["ok"] is False and out["data"] is None
    assert "safety rule" in out["error"].lower()


def test_run_agent_stops_at_max_steps():
    # Mock model asks for a tool on every turn, so it can never finish on its own.
    looping = {"role": "assistant", "content": "",
               "tool_calls": [{"function": {"name": "listing_detail", "arguments": {"listing_id": 1}}}]}
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "runs.jsonl"
        res = run_agent("loop forever", model=MockModel([looping]), max_steps=3,
                        execute=fake_execute_ok, log_path=log, verbose=False)
        assert res["stop_reason"] == "max_steps"
        assert res["steps"] == 3 and res["tool_calls"] == 3
        assert log.exists() and '"type": "final"' in log.read_text()


# Extra checks for the harness itself (optional but cheap)
def test_run_agent_completes_normally():
    msgs = [{"role": "assistant", "content": "",
             "tool_calls": [{"function": {"name": "listing_detail", "arguments": {"listing_id": 4}}}]},
            {"role": "assistant", "content": "Listing 4 is an apartment."}]
    res = run_agent("details of 4", model=MockModel(msgs), execute=fake_execute_ok, log_path=None, verbose=False)
    assert res["stop_reason"] == "completed" and res["tool_calls"] == 1 and res["steps"] == 2


def test_run_agent_stops_on_safety_block():
    msg = {"role": "assistant", "content": "",
           "tool_calls": [{"function": {"name": "listing_summary", "arguments": {"category": "x"}}}]}
    res = run_agent("owner email", model=MockModel([msg]), execute=fake_execute_blocked,
                    log_path=None, verbose=False)
    assert res["stop_reason"] == "safety_block" and res["tool_calls"] == 1


def test_coerce_args_fixes_string_numbers():
    assert coerce_args("search_listings", {"limit": "10", "query": "None"}) == {
        "limit": 10}
    assert coerce_args("listing_detail", {"listing_id": "4"}) == {"listing_id": 4}
    assert coerce_args("listing_summary", {"category": "Apartment", "include_private": "true"}) == {
        "category": "Apartment", "include_private": True}


TESTS = [test_execute_tool_blocks_safety_violation, test_run_agent_stops_at_max_steps,
         test_run_agent_completes_normally, test_run_agent_stops_on_safety_block, test_coerce_args_fixes_string_numbers]


def main() -> None:
    print(f"Student: {STUDENT}")
    passed = 0
    for t in TESTS:
        try:
            t()
            print(f"PASS | {t.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL | {t.__name__} :: {type(exc).__name__}: {exc}")
    print(f"SUMMARY: {passed}/{len(TESTS)} PASS")


if __name__ == "__main__":
    main()
