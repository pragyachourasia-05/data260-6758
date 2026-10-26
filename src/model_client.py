from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama


class ModelClient:
    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        verbose: bool = True,
        **llm_kwargs: Any,
    ):
        # llm_kwargs passes extra ChatOllama options through (HW6 uses
        # num_ctx, seed and format="json") without changing older callers.
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            **llm_kwargs,
        )
        self.verbose = verbose
        self.turn_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def complete(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        converted = []

        for message in messages:
            role = message["role"]
            content = message["content"]

            if role == "system":
                converted.append(SystemMessage(content=content))
            elif role == "user":
                converted.append(HumanMessage(content=content))
            elif role == "tool":
                # HW7: tool results go back to the model as tool-role messages.
                converted.append(ToolMessage(content=content, tool_call_id=message.get("tool_call_id", "")))
            else:
                converted.append(AIMessage(content=content, tool_calls=message.get("tool_calls") or []))

        llm = self.llm.bind_tools(tools) if tools else self.llm
        response = llm.invoke(converted)
        metadata = response.response_metadata or {}

        input_tokens = int(metadata.get("prompt_eval_count", 0) or 0)
        output_tokens = int(metadata.get("eval_count", 0) or 0)
        total_tokens = input_tokens + output_tokens

        self.turn_count += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        if self.verbose:
            print(f"Input tokens: {input_tokens}")
            print(f"Output tokens: {output_tokens}")
            print(f"Total tokens: {total_tokens}")

        return {
            "text": response.content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cached_input_tokens": int(metadata.get("prompt_eval_cached_count", 0) or 0),
            # HW7: parsed tool calls [{name, args, id}] and ones whose arguments failed to parse
            "tool_calls": [
                {"name": c["name"], "args": c["args"], "id": c.get("id") or ""}
                for c in (getattr(response, "tool_calls", None) or [])
            ],
            "invalid_tool_calls": [
                {"name": c.get("name"), "args": c.get("args"), "error": c.get("error")}
                for c in (getattr(response, "invalid_tool_calls", None) or [])
            ],
        }

    def stats(self, conversation: List[Dict[str, str]]) -> Dict[str, int]:
        history_length = len(str(conversation))

        return {
            "turn_count": self.turn_count,
            "cumulative_input_tokens": self.total_input_tokens,
            "cumulative_output_tokens": self.total_output_tokens,
            "cumulative_total_tokens": (
                self.total_input_tokens + self.total_output_tokens
            ),
            "serialized_history_length": history_length,
        }