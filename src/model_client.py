import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama


class ModelClient:
    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
    ):
        self.llm = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
        )
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
            else:
                converted.append(AIMessage(content=content))

        response = self.llm.invoke(converted)
        metadata = response.response_metadata or {}

        input_tokens = int(metadata.get("prompt_eval_count", 0) or 0)
        output_tokens = int(metadata.get("eval_count", 0) or 0)
        total_tokens = input_tokens + output_tokens

        self.turn_count += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        print(f"Input tokens: {input_tokens}")
        print(f"Output tokens: {output_tokens}")
        print(f"Total tokens: {total_tokens}")

        return {
            "text": response.content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
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