"""Part 5 agent harness with an offline MockModel and optional Ollama model."""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.execute_tool import execute_tool


class MockModel:
    def __init__(self, calls=10):
        self.calls = calls

    def next_action(self, user_input, history):
        return {"tool": "search_listings", "inputs": {"query": "Apartment"}}


class OllamaModel:
    def __init__(self, model="llama3.2:3b", base_url="http://localhost:11434"):
        self.model, self.base_url = model, base_url

    def next_action(self, user_input, history):
        import urllib.request
        prompt = "Return JSON only with keys tool and inputs. Available tools: search_listings(query,limit), listing_detail(listing_id), listing_summary(category). User: " + user_input
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode()
        request = urllib.request.Request(self.base_url + "/api/generate", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=60) as response:
            text = json.load(response)["response"]
        return json.loads(text[text.find("{"):text.rfind("}") + 1])


def run_agent(user_input: str, model=None, max_steps=3, log_path="reports/hw05/raw/agent_runs.jsonl"):
    model = model or OllamaModel()
    history = []
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stop_reason = "max_steps"
    for step in range(1, max_steps + 1):
        action = model.next_action(user_input, history)
        result = execute_tool(action.get("tool", ""), action.get("inputs", {}))
        event = {"timestamp": time.time(), "step": step, "user_input": user_input, "tool": action.get("tool"), "inputs": action.get("inputs", {}), "result": json.loads(result)}
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event) + "\n")
        history.append(event)
        if event["result"]["ok"] is False:
            stop_reason = "tool_error_or_safety_block"
            break
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"timestamp": time.time(), "final": True, "stop_reason": stop_reason, "steps": len(history), "tool_calls": len(history)}) + "\n")
    return {"steps": len(history), "stop_reason": stop_reason, "tool_calls": len(history), "history": history}


def offline_max_step_test():
    result = run_agent("find an apartment", MockModel(), max_steps=2, log_path="reports/hw05/raw/agent_test.jsonl")
    assert result["steps"] == 2 and result["stop_reason"] == "max_steps"


if __name__ == "__main__":
    print(json.dumps(run_agent("find an apartment", max_steps=3), indent=2))
