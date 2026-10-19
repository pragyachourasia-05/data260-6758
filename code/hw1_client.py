import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.file_memory import (  # noqa: E402
    build_system_prompt,
    compact,
    count_memory_lines,
    dream,
    load_memory_files,
    needs_consolidation,
    read_last_consolidated,
)
from src.model_client import ModelClient  # noqa: E402

HELP = """Commands:
  /memory   show the current file-based memory (MEMORY.md) and its consolidation status
  /compact  consolidate MEMORY.md and shorten this conversation; prints before/after counts
  /dream    pick out durable facts from the recent conversation and add them to MEMORY.md
  /stats    token usage so far
  /help     show this help
  /quit     exit"""


def refresh_system_prompt(conversation):
    """Reload AGENT.md + MEMORY.md into the system message (index 0)."""
    agent_text, memory_text = load_memory_files()
    conversation[0] = {"role": "system", "content": build_system_prompt(agent_text, memory_text)}
    return memory_text


def show_memory():
    _, memory_text = load_memory_files()
    due, reasons = needs_consolidation(memory_text)
    print(memory_text.rstrip() or "(MEMORY.md is empty)")
    print(f"\n[{count_memory_lines(memory_text)} non-empty, non-comment lines; "
          f"last consolidated: {read_last_consolidated(memory_text) or 'never'}]")
    print(f"[consolidation required: {'yes - ' + '; '.join(reasons) if due else 'no'}]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--temperature", type=float, default=0.0)
    args = parser.parse_args()

    client = ModelClient(
        model=args.model,
        temperature=args.temperature,
    )
    json_client = ModelClient(model=args.model, temperature=0.0, verbose=False, format="json")

    conversation = [{"role": "system", "content": ""}]
    memory_text = refresh_system_prompt(conversation)

    print("HW1 client + HW6 file-based memory (AGENT.md + MEMORY.md)")
    print("Enter a request. Type /help for commands.")
    due, reasons = needs_consolidation(memory_text)
    if due:
        print(f"Note: MEMORY.md needs consolidation ({'; '.join(reasons)}). Run /compact.")

    while True:
        try:
            user_text = input("\nYou: ").strip()
        except EOFError:
            user_text = "/quit"
        if not user_text:
            continue

        if user_text == "/quit":
            print("\nFinal cumulative stats:")
            print(client.stats(conversation))
            break

        if user_text == "/help":
            print(HELP)
            continue

        if user_text == "/stats":
            print("\nStats:")
            print(client.stats(conversation))
            continue

        if user_text == "/memory":
            show_memory()
            continue

        if user_text == "/compact":
            result = compact(conversation, client)
            refresh_system_prompt(conversation)
            print(f"Conversation messages: {result['messages_before']} -> {result['messages_after']}")
            print(f"MEMORY.md lines (non-empty, non-comment): {result['memory_lines_before']} -> {result['memory_lines_after']}")
            print(f"MEMORY.md facts: {result['facts_before']} -> {result['facts_after']}")
            print(f"Duplicates merged: {len(result['duplicates_merged'])}")
            for c in result["contradictions"]:
                print(f"  contradiction {c['key']}: kept \"{c['kept']}\" over \"{c['dropped']}\" ({c['rule']})")
            for r in result["needs_review"]:
                print(f"  NEEDS REVIEW {r['key']}: {r['reason']}")
            continue

        if user_text == "/dream":
            added = dream(conversation, json_client)
            refresh_system_prompt(conversation)
            if added:
                print(f"Added {len(added)} fact(s) to MEMORY.md:")
                print("\n".join(added))
            else:
                print("No new durable facts found.")
            continue

        conversation.append({"role": "user", "content": user_text})

        result = client.complete(conversation)
        assistant_text = result["text"]

        conversation.append(
            {"role": "assistant", "content": assistant_text}
        )

        print("\nAssistant:")
        print(assistant_text)


if __name__ == "__main__":
    main()
