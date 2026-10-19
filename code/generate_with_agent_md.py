"""HW6 Part 4.4: generate one function with AGENT.md + MEMORY.md as the system prompt.

Run from the repository root (Ollama running):
    python code/generate_with_agent_md.py
Writes src/generated/rent_parser.py, tests/test_rent_parser.py and the raw model
reply to reports/hw06/raw/agent_md_generation.json. Then run
    python code/check_agent_md_rules.py
to verify the result against the AGENT.md rules.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.file_memory import build_system_prompt, load_memory_files  # noqa: E402
from src.model_client import ModelClient  # noqa: E402

TASK = """Write a Python module for this repository containing one function:

parse_monthly_rent(text) -> converts a rent string from a listing into whole US dollars per month.
Examples: "$2,400/mo" -> 2400, "2400 per month" -> 2400, "$2.4k" -> 2400, "  $1,950 " -> 1950.
Empty strings, text without a number, negative or zero amounts must be rejected.

Then write the pytest test file for it. The tests import the function with:
from src.generated.rent_parser import parse_monthly_rent

Follow every rule in your instructions. Reply with exactly two ```python fenced code blocks:
first the module, second the test file. No other text."""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.2:3b")
    args = ap.parse_args()

    agent_text, memory_text = load_memory_files()
    system = build_system_prompt(agent_text, memory_text)
    client = ModelClient(model=args.model, temperature=0.0, seed=6758)
    result = client.complete([{"role": "system", "content": system}, {"role": "user", "content": TASK}])

    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", result["text"], flags=re.DOTALL)
    out_dir = ROOT / "reports" / "hw06" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "agent_md_generation.json").write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "task": TASK,
        "reply": result["text"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
    }, indent=2), encoding="utf-8")

    if len(blocks) < 2:
        print(f"Expected 2 code blocks, got {len(blocks)}. Raw reply saved to agent_md_generation.json.")
        sys.exit(1)
    module_path = ROOT / "src" / "generated" / "rent_parser.py"
    test_path = ROOT / "tests" / "test_rent_parser.py"
    module_path.parent.mkdir(parents=True, exist_ok=True)
    (module_path.parent / "__init__.py").touch()
    module_path.write_text(blocks[0].strip() + "\n", encoding="utf-8")
    test_path.write_text(blocks[1].strip() + "\n", encoding="utf-8")
    print(f"wrote {module_path.relative_to(ROOT)} and {test_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
