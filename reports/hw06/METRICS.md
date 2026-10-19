# HW6 METRICS

SID4 6758 | PORT_BASE 8458 | PREFIX s6758 | SEED 6758 | VERIFY_SEED 266758 | DOMAIN_ID 6 (rental housing listings)
Model: llama3.2:3b (Q4_K_M) via Ollama, temperature 0, seed 6758, num_ctx 8192 | Hardware: Intel Core i5-1335U, 16 GB RAM, Intel Iris Xe (CPU inference, no discrete GPU)

## Part 2 - memory demo session (12 messages, user `pragya`)

| Turn | Window msgs | Episodic facts retrieved | New facts | Summary | Prompt tokens |
| --- | --- | --- | --- | --- | --- |
| 1 | 0 | 0 | 2 | - | 151 |
| 2 | 2 | 1 | 1 | - | 254 |
| 3 | 4 | 3 | 1 | - | 374 |
| 4 | 6 | 3 | 2 | session | 443 |
| 5 | 8 | 3 | 2 | - | 611 |
| 6 | 10 | 3 | 1 | - | 704 |
| 7 | 12 | 3 | 3 | - | 791 |
| 8 | 12 | 3 | 1 | session + lifetime | 828 |
| 9 | 12 | 3 | 1 | - | 934 |
| 10 | 12 | 3 | 1 | - | 970 |
| 11 | 12 | 3 | 0 | - | 956 |
| 12 | 12 | 3 | 2 | session | 1046 |

Final recall question: "What's my cat's name and what's my current budget?" -> "Your cat's name is Miso, and your current budget is $2,700/month."

## Part 3 - what memory costs

Same 30-message conversation (`cases/conversation_30.yaml`) per setting, fresh user each time, then the 5 probes in `memory_probes.yaml`. Means are over the 30 conversation turns; latency is the full `/api/chat` request (prompt assembly + model reply + episode extraction + summarization).

| Setting | Mean prompt tokens/turn | Mean latency (ms) | Probe quality (1-5) |
| --- | --- | --- | --- |
| SHORT_TERM_N=4 | 501.2 | 30183 | 3.4 |
| SHORT_TERM_N=12 | 1001.6 | 58552 | 3.8 |
| SHORT_TERM_N=30 | 1750.4 | 71053 | 4.6 |
| Eviction/compression policy (N=30, compress_assistant) | 820.0 | 33276 | 4.6 |

### Supporting detail

| Setting | Median latency (ms) | Mean model-call latency (ms) | Mean completion tokens | Window tokens (est.) | Summary tokens (est.) | Episodic tokens (est.) | Probe scores P1-P5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SHORT_TERM_N=4 | 25090 | 17923 | 83.8 | 208 | 108 | 44 | [3, 1, 5, 5, 3] |
| SHORT_TERM_N=12 | 61827 | 43496 | 116.4 | 768 | 105 | 44 | [5, 2, 4, 5, 3] |
| SHORT_TERM_N=30 | 83916 | 56770 | 111.2 | 1523 | 141 | 44 | [5, 5, 5, 5, 3] |
| Eviction/compression policy (N=30, compress_assistant) | 36552 | 22323 | 51.3 | 472 | 92 | 44 | [5, 5, 5, 5, 3] |

Component token counts are estimates (characters / 4); prompt tokens are Ollama's real `prompt_eval_count`. Per-turn rows: `raw/part3_turns.csv`.

### Probe results

| Probe | SHORT_TERM_N=4 | SHORT_TERM_N=12 | SHORT_TERM_N=30 | Eviction/compression policy |
| --- | --- | --- | --- | --- |
| P1_ev_charging | 3 | 5 | 5 | 5 |
| P2_visitor | 1 | 2 | 5 | 5 |
| P3_current_budget | 5 | 4 | 5 | 5 |
| P4_cat_name | 5 | 5 | 5 | 5 |
| P5_move_in | 3 | 3 | 3 | 3 |

### Memory-saving policy: `compress_assistant`

Keeps every user message in the N=30 window verbatim and cuts older assistant replies (all but the last two window messages) to their first sentence, max 25 words (`backend/app/memory.py:apply_policy`).

| | N=30 baseline | N=30 + compress_assistant | Change |
| --- | --- | --- | --- |
| Mean prompt tokens/turn | 1750.4 | 820.0 | -930.4 (53.2% saved) |
| Mean latency (ms) | 71053 | 33276 | -37777 |
| Probe quality | 4.6 | 4.6 | +0.0 |

### Cost estimate: 10,000 conversations x 30 turns

Input $1 / 1M tokens, output $5 / 1M tokens. "Chat" = the `/api/chat` reply calls; "+ memory upkeep" also counts the episode-extraction and summarization calls each turn makes.

| Setting | Input tokens / conv. | Output tokens / conv. | Chat cost (10k conv.) | + memory upkeep (10k conv.) | Probe quality |
| --- | --- | --- | --- | --- | --- |
| SHORT_TERM_N=4 | 15,037 | 2,515 | $276.12 | $419.83 | 3.4 |
| SHORT_TERM_N=12 | 30,047 | 3,491 | $475.02 | $626.65 | 3.8 |
| SHORT_TERM_N=30 | 52,513 | 3,336 | $691.93 | $854.33 | 4.6 |
| Eviction/compression policy (N=30, compress_assistant) | 24,600 | 1,538 | $322.90 | $450.02 | 4.6 |

**Best setting: Eviction/compression policy (N=30, compress_assistant)** - $450.02 for 10,000 conversations (chat only $322.90).
**Worst setting: SHORT_TERM_N=30** - $854.33 (chat only $691.93).

How they were selected: first by probe quality, then by cost. Best = the cheapest setting among those with the highest mean probe score; worst = the most expensive setting. The cheapest settings overall (small N) are not "best" because they lose facts that only the window holds (P2 visitor). The most expensive setting buys no extra quality over the compressed one, so it is the worst value.

## Part 4 - file-based memory

| MEMORY.md | Total lines | Non-empty, non-comment lines |
| --- | --- | --- |
| Original (`memory/MEMORY_original.md`) | 55 | 50 |
| After /compact (`memory/MEMORY_consolidated.md`) | 36 | 34 |

/compact output (`raw/part4_compact_session.txt`): conversation messages 7 -> 6, MEMORY.md lines 50 -> 34, facts 46 -> 22, 17 duplicate groups merged, 5 contradictions resolved, 1 flagged for review (`mongo_db`).

| Generated function check (`code/check_agent_md_rules.py`) | Passed |
| --- | --- |
| Model output as generated (`raw/agent_md_generated_v1/`) | 9/10 |
| After correction (`src/generated/rent_parser.py`) | 10/10 |
