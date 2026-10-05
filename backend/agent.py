"""Part 5: agent loop around the three domain tools.

run_agent(user_input) talks to a local Ollama model, executes tool calls ONLY
through execute_tool (Part 4), enforces max_steps, and logs every step to
agent_runs.jsonl.

Stop reasons:
  completed     model answered without asking for another tool
  max_steps     step ceiling reached while the model still wanted tools
  safety_block  execute_tool refused a call (business safety rule); harness stops
  model_error   the model could not be reached or returned something unusable
"""
from __future__ import annotations

import ast
import importlib
import json
import os
import sys
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SID4 = 6758
SEED = SID4
DEFAULT_LOG = ROOT / "reports" / "hw05" / "raw" / "agent_runs.jsonl"
DEFAULT_MAX_STEPS = 6

SYSTEM_PROMPT = (
    "You are a rental-housing assistant. Use the provided tools to answer; "
    "never invent listings, prices, ids or owners. If a tool returns an error, "
    "explain it briefly instead of guessing. Private owner data is not available. "
    "When you have enough information, answer concisely without calling more tools."
)

# ---------------------------------------------------------------------------
# ALIGN THESE THREE SCHEMAS WITH YOUR MCP SERVER'S TOOL PARAMETERS.
# The names below match your Inspector screenshots (search_listings,
# listing_detail, listing_summary). Rename or add parameters if your tools differ.
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_listings",
            "description": "Search rental listings. Use when the user wants to find or browse listings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to match, e.g. a street or city"},
                    "limit": {"type": "integer", "description": "Max results, 1 to 50"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listing_detail",
            "description": "Get full details for one listing by its numeric id.",
            "parameters": {
                "type": "object",
                "properties": {"listing_id": {"type": "integer", "description": "Listing id, positive integer"}},
                "required": ["listing_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listing_summary",
            "description": "Aggregate statistics (count, average monthly rent) for a property category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Property category, e.g. Apartment"},
                    "include_private": {"type": "boolean",
                                        "description": "Set true only if the user asks for private owner data (default false)"},
                },
                "required": ["category"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Model clients
# ---------------------------------------------------------------------------
class OllamaClient:
    """The only place that talks to Ollama."""

    def __init__(self, model: str | None = None, host: str | None = None, timeout: float = 180.0):
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3:8b")
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": 0, "seed": SEED},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body["message"]


class MockModel:
    """Scripted model for offline tests. `script` is a list of assistant messages.
    When the script runs out, the last message repeats (so a tool-calling
    script never finishes, which is how the max_steps test works)."""

    def __init__(self, script: list[dict]):
        self.script = script
        self.calls = 0

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        msg = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return msg


# ---------------------------------------------------------------------------
# execute_tool discovery (so this file works with whatever you named your Part 4 module)
# ---------------------------------------------------------------------------
def load_execute_tool():
    """Import execute_tool from EXECUTE_TOOL_MODULE, or find the backend file that defines it."""
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    wanted = os.getenv("EXECUTE_TOOL_MODULE")
    candidates = [wanted] if wanted else []
    if not wanted:
        for path in sorted(HERE.glob("*.py")):
            if path.name in {"agent.py", "run_scenarios.py", "test_part5.py"}:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            if any(isinstance(n, ast.FunctionDef) and n.name == "execute_tool" for n in tree.body):
                candidates.append(path.stem)
    for name in candidates:
        try:
            return getattr(importlib.import_module(name), "execute_tool")
        except (ImportError, AttributeError):
            continue
    raise ImportError(
        "Could not find execute_tool. Set EXECUTE_TOOL_MODULE to the module that defines it "
        "(for example: $env:EXECUTE_TOOL_MODULE='mcp_domain_server')."
    )


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _log(path: Path | None, record: dict) -> None:
    if path is None:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _parse_args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}



def coerce_args(name: str, args: dict) -> dict:
    """Repair common small-model mistakes before calling execute_tool:
    numeric strings for integer parameters ("10" -> 10) and placeholder strings
    ("", "None", "null") for optional parameters (dropped). Types and required
    fields are still validated by execute_tool itself."""
    props = next((t["function"]["parameters"]["properties"] for t in TOOLS
                  if t["function"]["name"] == name), None)
    if props is None:
        return args
    out = {}
    for key, val in args.items():
        if val is None or (isinstance(val, str) and val.strip().lower() in {"", "none", "null", "n/a"}):
            continue
        if props.get(key, {}).get("type") == "integer":
            if isinstance(val, str):
                try:
                    val = int(float(val.strip())) if float(val.strip()).is_integer() else val
                except ValueError:
                    pass
            elif isinstance(val, float) and val.is_integer():
                val = int(val)
        elif props.get(key, {}).get("type") == "boolean" and isinstance(val, str):
            if val.strip().lower() in {"true", "yes"}:
                val = True
            elif val.strip().lower() in {"false", "no"}:
                val = False
        out[key] = val
    return out


def _is_safety_block(result_json: str) -> bool:
    try:
        data = json.loads(result_json)
    except (TypeError, json.JSONDecodeError):
        return False
    return data.get("ok") is False and "safety rule" in str(data.get("error", "")).lower()


def run_agent(
    user_input: str,
    model=None,
    max_steps: int = DEFAULT_MAX_STEPS,
    execute=None,
    log_path: Path | str | None = DEFAULT_LOG,
    scenario: str | None = None,
    verbose: bool = True,
) -> dict:
    """Run one agent episode. Returns a summary dict (also logged to JSONL)."""
    model = model or OllamaClient()
    execute = execute or load_execute_tool()
    log_path = Path(log_path) if log_path else None
    run_id = uuid.uuid4().hex[:8]
    base = {"run_id": run_id, "scenario": scenario}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    _log(log_path, {**base, "ts": _now(), "type": "start", "user_input": user_input, "max_steps": max_steps})

    step = 0
    tool_calls_total = 0
    final_text = ""
    stop_reason = "max_steps"

    while step < max_steps:
        step += 1
        try:
            msg = model.complete(messages, TOOLS)
        except Exception as exc:  # network, bad JSON, missing model
            stop_reason = "model_error"
            final_text = f"Model error: {exc}"
            _log(log_path, {**base, "ts": _now(), "type": "model_error", "step": step, "error": str(exc)})
            break

        calls = msg.get("tool_calls") or []
        _log(log_path, {**base, "ts": _now(), "type": "model_response", "step": step,
                        "content": msg.get("content", ""), "n_tool_calls": len(calls)})

        if not calls:
            final_text = msg.get("content", "") or ""
            stop_reason = "completed"
            break

        messages.append(msg)
        blocked = False
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            raw_args = _parse_args(fn.get("arguments"))
            args = coerce_args(name, raw_args)
            result = execute(name, args)
            tool_calls_total += 1
            if verbose:
                print(f"  step {step} | tool call {tool_calls_total}: {name}({json.dumps(args)})")
            _log(log_path, {**base, "ts": _now(), "type": "tool_call", "step": step,
                            "tool": name, "input": args, "input_raw": raw_args, "result": result})
            messages.append({"role": "tool", "tool_name": name, "content": result})
            if _is_safety_block(result):
                blocked = True
                final_text = f"Request stopped by a safety rule: {json.loads(result).get('error')}"
                break
        if blocked:
            stop_reason = "safety_block"
            break
    else:
        stop_reason = "max_steps"
        final_text = final_text or f"Stopped after reaching max_steps={max_steps}."

    summary = {
        "run_id": run_id,
        "scenario": scenario,
        "steps": step,
        "tool_calls": tool_calls_total,
        "stop_reason": stop_reason,
        "final": final_text,
    }
    _log(log_path, {**base, "ts": _now(), "type": "final", **{k: summary[k] for k in ("steps", "tool_calls", "stop_reason", "final")}})
    return summary
