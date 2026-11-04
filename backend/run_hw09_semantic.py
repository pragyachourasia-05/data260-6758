"""HW9 Part 2 test: 12 queries through POST /qa (exact duplicates, paraphrases and new questions).

    python backend/run_hw09_semantic.py          run the queries (cold cache)
    python backend/run_hw09_semantic.py --show   print the saved results
"""
import json
import sys
from pathlib import Path

import redis
import requests

API = "http://127.0.0.1:8458/qa"
RAW = Path(__file__).resolve().parent.parent / "reports" / "hw09" / "raw"
OUT = RAW / "part2_semantic.json"
QUERIES = [
    ("new", "What is the monthly rent at 100 Research Avenue?"),
    ("exact duplicate", "What is the monthly rent at 100 Research Avenue?"),
    ("paraphrase", "How much is the rent per month for 100 Research Avenue?"),
    ("new", "What documents do landlords usually ask for on a rental application?"),
    ("exact duplicate", "What documents do landlords usually ask for on a rental application?"),
    ("paraphrase", "Which documents will a landlord usually want when I apply to rent?"),
    ("new", "What type of property is 101 Research Avenue?"),
    ("paraphrase", "Is 101 Research Avenue a house or an apartment?"),
    ("new", "Does renters insurance cover my belongings after a fire?"),
    ("paraphrase", "Will renters insurance pay for my stuff if there is a fire?"),
    ("new", "How many units are available at 102 Research Avenue?"),
    ("exact duplicate", "What type of property is 101 Research Avenue?"),
]


def show(results):
    print(f"{'#':>2} {'kind':16}{'is_cached':10}{'similarity':11}{'latency_ms':>11}  question")
    for i, r in enumerate(results, 1):
        print(f"{i:>2} {r['kind']:16}{str(r['is_cached']):10}{r['similarity']:<11.4f}{r['latency_ms']:>11.1f}  {r['question']}")
    hits = [r for r in results if r["is_cached"]]
    misses = [r for r in results if not r["is_cached"]]
    print(f"\nCache hit rate: {len(hits)}/{len(results)} = {len(hits) / len(results):.0%}")
    print(f"Average latency, cached:     {sum(r['latency_ms'] for r in hits) / max(1, len(hits)):.1f} ms")
    print(f"Average latency, not cached: {sum(r['latency_ms'] for r in misses) / max(1, len(misses)):.1f} ms")


def main():
    if "--show" in sys.argv:
        show(json.loads(OUT.read_text(encoding="utf-8")))
        return
    client = redis.Redis(port=6379)
    keys = list(client.scan_iter("s6758:semcache:*"))
    if keys:
        client.delete(*keys)
    results = []
    for kind, question in QUERIES:
        r = requests.post(API, json={"question": question}, timeout=900).json()
        r["kind"] = kind
        results.append(r)
        print(f"{kind:16} is_cached={r['is_cached']} similarity={r['similarity']} latency_ms={r['latency_ms']}  {question}",
              flush=True)
        RAW.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print()
    show(results)


if __name__ == "__main__":
    main()
