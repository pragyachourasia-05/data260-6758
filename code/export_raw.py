import json
import re
from pathlib import Path


def parse_file(path, temperature):
    text = Path(path).read_text(encoding="utf-16")
    blocks = re.split(r"===== TEMP [\d.]+ RUN \d+ =====", text)
    results = []

    for run_number, block in enumerate(blocks[1:], start=1):
        planner = re.search(r"--- Planner \((\d+) ms\)", block)
        reviewer = re.search(r"--- Reviewer \((\d+) ms\)", block)

        final_match = re.search(
            r"Finalized Output\s*\n(\{.*?\n\})\s*\n\n Publish Package",
            block,
            re.S,
        )

        if not final_match:
            continue

        final = json.loads(final_match.group(1))

        results.append({
            "run": run_number,
            "temperature": temperature,
            "tags": final["data"]["tags"],
            "summary": final["data"]["summary"],
            "issues": final["data"]["issues"],
            "planner_ms": int(planner.group(1)) if planner else None,
            "reviewer_ms": int(reviewer.group(1)) if reviewer else None,
        })

    return results


all_results = []
all_results.extend(parse_file("part3_temp07.txt", 0.7))
all_results.extend(parse_file("part3_temp00.txt", 0.0))

Path("reports/hw01/raw/non_determinism_results.json").write_text(
    json.dumps(all_results, indent=2),
    encoding="utf-8",
)

print(f"Wrote {len(all_results)} results.")