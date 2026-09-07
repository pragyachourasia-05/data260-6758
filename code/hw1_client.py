import argparse
from pathlib import Path

from src.model_client import ModelClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2:3b")
    parser.add_argument("--temperature", type=float, default=0.0)
    args = parser.parse_args()

    instructions = Path("AGENT.md").read_text(encoding="utf-8")

    client = ModelClient(
        model=args.model,
        temperature=args.temperature,
    )

    conversation = [
        {"role": "system", "content": instructions}
    ]

    print("Enter a request.")
    print("Commands: /stats, /quit")

    while True:
        user_text = input("\nYou: ").strip()

        if user_text == "/quit":
            print("\nFinal cumulative stats:")
            print(client.stats(conversation))
            break

        if user_text == "/stats":
            print("\nStats:")
            print(client.stats(conversation))
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