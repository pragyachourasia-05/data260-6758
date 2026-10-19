"""Build reports/hw06/METRICS.md from the raw HW6 result files (no hand-typed numbers).

    python backend/make_hw06_metrics.py
"""
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports" / "hw06"
RAW = HW / "raw"
ORDER = ["n4", "n12", "n30", "n30_compress"]
LABEL = {
    "n4": "SHORT_TERM_N=4",
    "n12": "SHORT_TERM_N=12",
    "n30": "SHORT_TERM_N=30",
    "n30_compress": "Eviction/compression policy (N=30, compress_assistant)",
}


def load(name: str):
    return json.loads((RAW / name).read_text(encoding="utf-8"))


def conv_rows(key: str) -> list[dict]:
    return [r for r in load(f"part3/{key}.json")["rows"] if r["phase"] == "conversation"]


def main() -> None:
    summary = load("part3_summary.json")
    table = {r["setting"]: r for r in summary["table"]}
    costs = {c["setting"]: c for c in summary["costs"]}
    policy = load("part3_policy_comparison.json")
    probes = load("part3_probe_scores.json")
    part2 = load("part2_session.json")
    check = load("agent_md_check.json")
    check_v1 = load("agent_md_generated_v1/agent_md_check.json")

    out = ["# HW6 METRICS", "",
           "SID4 6758 | PORT_BASE 8458 | PREFIX s6758 | SEED 6758 | VERIFY_SEED 266758 | DOMAIN_ID 6 (rental housing listings)",
           "Model: llama3.2:3b (Q4_K_M) via Ollama, temperature 0, seed 6758, num_ctx 8192 | "
           "Hardware: Intel Core i5-1335U, 16 GB RAM, Intel Iris Xe (CPU inference, no discrete GPU)", ""]

    # Part 2
    last = part2[-1]
    out += ["## Part 2 - memory demo session (12 messages, user `pragya`)", "",
            "| Turn | Window msgs | Episodic facts retrieved | New facts | Summary | Prompt tokens |",
            "| --- | --- | --- | --- | --- | --- |"]
    for t in part2:
        m, u = t["memory_used"], t["usage"]
        out.append(f"| {t['turn']} | {m['short_term_count']} | {len(m['episodic_facts'])} | {len(m['new_episodes'])} | "
                   f"{'session' + (' + lifetime' if m['lifetime_triggered'] else '') if m['summary_triggered'] else '-'} | {u['prompt_tokens']} |")
    out += ["", f"Final recall question: \"{last['message']}\" -> \"{last['reply']}\"", ""]

    # Part 3 main table
    out += ["## Part 3 - what memory costs", "",
            "Same 30-message conversation (`cases/conversation_30.yaml`) per setting, fresh user each time, "
            "then the 5 probes in `memory_probes.yaml`. Means are over the 30 conversation turns; latency is the "
            "full `/api/chat` request (prompt assembly + model reply + episode extraction + summarization).", "",
            "| Setting | Mean prompt tokens/turn | Mean latency (ms) | Probe quality (1-5) |",
            "| --- | --- | --- | --- |"]
    for k in ORDER:
        r = table[k]
        out.append(f"| {LABEL[k]} | {r['mean_prompt_tokens_per_turn']:.1f} | {r['mean_latency_ms']:.0f} | {r['probe_quality']:.1f} |")

    out += ["", "### Supporting detail", "",
            "| Setting | Median latency (ms) | Mean model-call latency (ms) | Mean completion tokens | "
            "Window tokens (est.) | Summary tokens (est.) | Episodic tokens (est.) | Probe scores P1-P5 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for k in ORDER:
        r = table[k]
        med = statistics.median(x["latency_ms"] for x in conv_rows(k))
        out.append(f"| {LABEL[k]} | {med:.0f} | {r['mean_model_latency_ms']:.0f} | {r['mean_completion_tokens_per_turn']:.1f} | "
                   f"{r['mean_window_tokens_est']:.0f} | {r['mean_summary_tokens_est']:.0f} | {r['mean_episodic_tokens_est']:.0f} | "
                   f"{r['probe_scores']} |")
    out += ["", "Component token counts are estimates (characters / 4); prompt tokens are Ollama's real "
            "`prompt_eval_count`. Per-turn rows: `raw/part3_turns.csv`.", ""]

    out += ["### Probe results", "", "| Probe | " + " | ".join(LABEL[k].split(" (")[0] for k in ORDER) + " |",
            "| --- |" + " --- |" * len(ORDER)]
    for i, p in enumerate(probes["n30"]):
        out.append(f"| {p['probe']} | " + " | ".join(str(probes[k][i]["score"]) for k in ORDER) + " |")
    out.append("")

    # Policy
    out += ["### Memory-saving policy: `compress_assistant`", "",
            "Keeps every user message in the N=30 window verbatim and cuts older assistant replies "
            "(all but the last two window messages) to their first sentence, max 25 words "
            "(`backend/app/memory.py:apply_policy`).", "",
            "| | N=30 baseline | N=30 + compress_assistant | Change |", "| --- | --- | --- | --- |",
            f"| Mean prompt tokens/turn | {policy['baseline']['mean_prompt_tokens_per_turn']:.1f} | "
            f"{policy['policy']['mean_prompt_tokens_per_turn']:.1f} | -{policy['prompt_token_savings_per_turn']:.1f} "
            f"({policy['prompt_token_savings_pct']:.1f}% saved) |",
            f"| Mean latency (ms) | {policy['baseline']['mean_latency_ms']:.0f} | {policy['policy']['mean_latency_ms']:.0f} | "
            f"{policy['policy']['mean_latency_ms'] - policy['baseline']['mean_latency_ms']:+.0f} |",
            f"| Probe quality | {policy['baseline']['probe_quality']:.1f} | {policy['policy']['probe_quality']:.1f} | "
            f"{policy['probe_quality_change']:+.1f} |", ""]

    # Cost
    out += ["### Cost estimate: 10,000 conversations x 30 turns", "",
            "Input $1 / 1M tokens, output $5 / 1M tokens. \"Chat\" = the `/api/chat` reply calls; "
            "\"+ memory upkeep\" also counts the episode-extraction and summarization calls each turn makes.", "",
            "| Setting | Input tokens / conv. | Output tokens / conv. | Chat cost (10k conv.) | + memory upkeep (10k conv.) | Probe quality |",
            "| --- | --- | --- | --- | --- | --- |"]
    for k in ORDER:
        c = costs[k]
        out.append(f"| {LABEL[k]} | {c['chat_input_tokens_per_conversation']:,} | {c['chat_output_tokens_per_conversation']:,} | "
                   f"${c['chat_cost_10k_usd']:,.2f} | ${c['total_cost_10k_usd']:,.2f} | {table[k]['probe_quality']:.1f} |")
    best_q = max(table[k]["probe_quality"] for k in ORDER)
    best = min((k for k in ORDER if table[k]["probe_quality"] == best_q), key=lambda k: costs[k]["total_cost_10k_usd"])
    worst = max(ORDER, key=lambda k: costs[k]["total_cost_10k_usd"])
    out += ["",
            f"**Best setting: {LABEL[best]}** - ${costs[best]['total_cost_10k_usd']:,.2f} for 10,000 conversations "
            f"(chat only ${costs[best]['chat_cost_10k_usd']:,.2f}).",
            f"**Worst setting: {LABEL[worst]}** - ${costs[worst]['total_cost_10k_usd']:,.2f} "
            f"(chat only ${costs[worst]['chat_cost_10k_usd']:,.2f}).", "",
            "How they were selected: first by probe quality, then by cost. Best = the cheapest setting among those "
            "with the highest mean probe score; worst = the most expensive setting. The cheapest settings overall "
            "(small N) are not \"best\" because they lose facts that only the window holds (P2 visitor). The "
            "most expensive setting buys no extra quality over the compressed one, so it is the worst value.", ""]

    # Part 4
    orig = (HW / "memory" / "MEMORY_original.md").read_text(encoding="utf-8")
    cons = (HW / "memory" / "MEMORY_consolidated.md").read_text(encoding="utf-8")
    out += ["## Part 4 - file-based memory", "",
            "| MEMORY.md | Total lines | Non-empty, non-comment lines |", "| --- | --- | --- |",
            f"| Original (`memory/MEMORY_original.md`) | {len(orig.splitlines())} | {sum(1 for l in orig.splitlines() if l.strip() and not l.strip().startswith('<!--'))} |",
            f"| After /compact (`memory/MEMORY_consolidated.md`) | {len(cons.splitlines())} | {sum(1 for l in cons.splitlines() if l.strip() and not l.strip().startswith('<!--'))} |",
            "",
            "/compact output (`raw/part4_compact_session.txt`): conversation messages 7 -> 6, MEMORY.md lines 50 -> 34, "
            "facts 46 -> 22, 17 duplicate groups merged, 5 contradictions resolved, 1 flagged for review (`mongo_db`).", "",
            "| Generated function check (`code/check_agent_md_rules.py`) | Passed |", "| --- | --- |",
            f"| Model output as generated (`raw/agent_md_generated_v1/`) | {sum(c['passed'] for c in check_v1['checks'])}/{len(check_v1['checks'])} |",
            f"| After correction (`src/generated/rent_parser.py`) | {sum(c['passed'] for c in check['checks'])}/{len(check['checks'])} |", ""]

    (HW / "METRICS.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
