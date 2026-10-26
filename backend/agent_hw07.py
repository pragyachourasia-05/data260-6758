"""HW7 Part 2: hand-written agent loop over the three HW5 domain tools.

run_agent(user_input) calls the local model through the HW1 adapter (src/model_client.ModelClient),
executes tool calls through execute_tool, appends results as tool-role messages, and continues
until the model gives a final answer or a hard step ceiling is reached.

Repair path: an unknown tool name, unparseable arguments, a schema violation, plain text when a
tool was still required, or a chain that stops early is answered with ONE specific corrective
message per problem; after MAX_REPAIRS failed repairs the run stops cleanly (stop_reason
"repair_failed") instead of looping.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for p in (str(HERE), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.execute_tool import execute_tool  # noqa: E402
from src.model_client import ModelClient  # noqa: E402

MODEL = "llama3.2:3b"
TEMPERATURE = 0.7      # same settings for every run; > 0 so repeated attempts can differ
MAX_STEPS = 8          # hard iteration ceiling (model calls per run)
MAX_REPAIRS = 2        # corrective reprompts allowed per run

SYSTEM_PROMPT = (
    "You are a rental-housing assistant. Answer ONLY with facts returned by the tools; never invent "
    "listings, ids, prices or addresses. Use one tool call at a time and keep calling tools until "
    "every step of the user's request is done, then give a short final answer that quotes the "
    "values you used. If a tool returns an error, explain it briefly instead of guessing."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "search_listings",
        "description": "Search rental listings by text (address, category such as Apartment or House, or listing code).",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Text to match, e.g. Apartment"},
            "limit": {"type": "integer", "description": "Max results, 1 to 50"},
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "listing_detail",
        "description": "Full details (rent, units, owner) for one listing. Pass the numeric `id` field from "
                       "search results (e.g. 2), NOT the listing_code (e.g. L-6758-002).",
        "parameters": {"type": "object", "properties": {
            "listing_id": {"type": "integer", "description": "The numeric id field of the listing, e.g. 2"},
        }, "required": ["listing_id"]},
    }},
    {"type": "function", "function": {
        "name": "listing_summary",
        "description": "Count and average monthly rent for a property category (or all listings).",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string", "description": "Property category, e.g. Apartment"},
        }, "required": []},
    }},
]
SCHEMAS = {t["function"]["name"]: t["function"]["parameters"] for t in TOOLS}
PY_TYPES = {"string": str, "integer": int, "boolean": bool, "number": (int, float)}


def coerce(name: str, args: dict, schemas: dict | None = None) -> dict:
    """Small, safe repairs before validation: "2" -> 2 for integer fields, drop null-like optionals."""
    props = (schemas or SCHEMAS).get(name, {}).get("properties", {})
    out = {}
    for key, val in args.items():
        if val is None or (isinstance(val, str) and val.strip().lower() in {"", "none", "null"}):
            continue
        if props.get(key, {}).get("type") == "integer" and isinstance(val, str) and val.strip().isdigit():
            val = int(val.strip())
        elif props.get(key, {}).get("type") == "integer" and isinstance(val, float) and val.is_integer():
            val = int(val)
        out[key] = val
    return out


def validate_call(name: str, args: Any, schemas: dict | None = None) -> tuple[str, str] | None:
    """Return (failure_type, specific problem) or None when the call matches the tool schema."""
    schemas = schemas or SCHEMAS
    if name not in schemas:
        return "unknown_tool", f"there is no tool named '{name}'; available tools: {', '.join(schemas)}"
    if not isinstance(args, dict):
        return "malformed_arguments", f"arguments for {name} must be a JSON object"
    schema = schemas[name]
    missing = [k for k in schema["required"] if k not in args]
    if missing:
        return "malformed_arguments", f"{name} is missing required argument(s): {', '.join(missing)}"
    extra = [k for k in args if k not in schema["properties"]]
    if extra:
        return "malformed_arguments", f"{name} does not accept argument(s): {', '.join(extra)}"
    for key, val in args.items():
        want = schema["properties"][key]["type"]
        if isinstance(val, bool) and want != "boolean" or not isinstance(val, PY_TYPES[want]):
            return "malformed_arguments", f"{name}.{key} must be of type {want}, got {type(val).__name__} {val!r}"
    return None


def _summ(result_json: str) -> str:
    try:
        r = json.loads(result_json)
    except json.JSONDecodeError:
        return result_json[:80]
    if not (r.get("ok") or r.get("success")):  # domain tools use "ok", file tools use "success"
        return f"error: {r.get('error')}"
    data = r.get("data")
    if isinstance(data, dict):
        for key in ("files", "matches"):
            if key in data:
                return f"ok, {len(data[key])} {key}"
    return f"ok, {len(data)} row(s)" if isinstance(data, list) else "ok"


def run_agent(
    user_input: str,
    model: Any = None,
    required_tools: list[str] | None = None,
    extra_context: list[dict] | None = None,
    max_steps: int = MAX_STEPS,
    max_repairs: int = MAX_REPAIRS,
    max_tool_calls: int | None = None,
    max_tokens: int | None = None,
    log: Callable[[str], None] = print,
    tools: list[dict] | None = None,
    execute: Callable[[str, dict], str] | None = None,
    system_prompt: str | None = None,
) -> dict:
    """Run one episode. `required_tools` (from the fixed case) lets the loop detect a lost chain.

    `extra_context` is appended as user-role messages (Part 3 uses it for reflections, which
    therefore never change the system prompt or the tool list).
    """
    tools = tools or TOOLS
    execute = execute or execute_tool
    schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
    model = model or ModelClient(model=MODEL, temperature=TEMPERATURE, verbose=False, num_ctx=4096,
                                  num_predict=512, client_kwargs={"timeout": 300})
    required = list(required_tools or [])
    messages: list[dict] = [{"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                            {"role": "user", "content": user_input}]
    messages += extra_context or []

    t0 = time.perf_counter()
    trace: list[dict] = []          # every tool invocation (tool, input, result)
    failures: list[dict] = []       # every problem the repair path answered
    proposed = well_formed = 0      # tool-call proposals and how many were valid as proposed
    tokens = repairs = steps = 0
    final, stop = "", "max_steps"

    def repair(kind: str, problem: str) -> bool:
        nonlocal repairs
        failures.append({"type": kind, "problem": problem, "step": steps})
        log(f"  [repair {repairs + 1}/{max_repairs}] {kind}: {problem}")
        repairs += 1
        return repairs <= max_repairs

    while steps < max_steps:
        steps += 1
        resp = model.complete(messages, tools)
        tokens += resp["total_tokens"]
        calls, invalid = resp["tool_calls"], resp["invalid_tool_calls"]

        if invalid:  # arguments that were not valid JSON
            proposed += len(invalid)
            bad = invalid[0]
            if not repair("malformed_arguments", f"arguments for {bad['name']} are not valid JSON ({bad['error']})"):
                stop = "repair_failed"
                break
            messages.append({"role": "assistant", "content": resp["text"] or ""})
            messages.append({"role": "user", "content": f"Your tool call failed: arguments for {bad['name']} were not "
                             "valid JSON. Call the tool again with a JSON object that matches its schema."})
            continue

        if not calls:
            used = {t["tool"] for t in trace if t["ok_call"]}
            still = [t for t in required if t not in used]
            if still:
                kind = "text_instead_of_tool" if not trace else "lost_chain"
                if not repair(kind, f"answered in text but the task still needs: {', '.join(still)}"):
                    stop = "repair_failed"
                    final = resp["text"]
                    break
                messages.append({"role": "assistant", "content": resp["text"] or ""})
                messages.append({"role": "user", "content": "The task is not finished. Do not answer yet: call "
                                 f"{still[0]} next, using the results you already have."})
                continue
            final, stop = resp["text"], "completed"
            break

        if len(calls) > 1:
            # One call per turn: a small model otherwise "chains" calls inside one turn and passes
            # placeholders (e.g. listing_id="search_listings") before it has seen any result.
            log(f"  [one call per turn] running {calls[0]['name']}, deferring {len(calls) - 1} more")
            calls = calls[:1]
        messages.append({"role": "assistant", "content": resp["text"] or "", "tool_calls": calls})
        for call in calls:
            proposed += 1
            name, args = call["name"], coerce(call["name"], call["args"] if isinstance(call["args"], dict) else {}, schemas)
            problem = validate_call(name, args, schemas)
            if problem:
                ok = repair(*problem)
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": json.dumps({"ok": False, "error": f"INVALID CALL: {problem[1]}. "
                                                        "Fix the call and try again."})})
                trace.append({"tool": name, "input": args, "result": "rejected before execution", "ok_call": False})
                if not ok:
                    stop = "repair_failed"
                    break
                continue
            well_formed += 1
            result = execute(name, args)
            trace.append({"tool": name, "input": args, "result": result, "ok_call": True})
            log(f"  [tool {len([t for t in trace if t['ok_call']])}] {name}({json.dumps(args)}) -> {_summ(result)}")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
        if stop == "repair_failed":
            break
        n_calls = len([t for t in trace if t["ok_call"]])
        if (max_tool_calls and n_calls >= max_tool_calls) or (max_tokens and tokens >= max_tokens):
            stop = "budget_exhausted"
            break

    used = {t["tool"] for t in trace if t["ok_call"]}
    if stop == "completed" and any(t not in used for t in required):
        failures.append({"type": "lost_chain", "problem": "finished without every required tool", "step": steps})
    total_calls = len([t for t in trace if t["ok_call"]])
    log(f"  total tool calls: {total_calls} | stop: {stop} | steps: {steps} | repairs: {repairs}")
    return {
        "final": final,
        "stop_reason": stop,
        "steps": steps,
        "tool_calls": total_calls,
        "proposed_calls": proposed,
        "well_formed_as_proposed": well_formed,
        "repairs": repairs,
        "failures": failures,
        "trace": trace,
        "tokens": tokens,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
