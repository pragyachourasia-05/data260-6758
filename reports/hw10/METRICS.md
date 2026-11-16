# HW10 Metrics

## Part 2 - Evaluator (judge llama3.2:3b, GEval, scale 1-5)

| Criterion | Mean | n |
| --- | --- | --- |
| Plan Quality | 3.96 | 52 |
| Writer Helpfulness | 3.23 | 52 |
| Final Answer Helpfulness | 3.23 | 52 |

Final answer identical to the draft in 52 of 52 requests.

## Part 3 - Judge vs my labels (20 drafts, 3 runs)

| Run | Spearman rho | p | Mean abs difference |
| --- | --- | --- | --- |
| run1 | 0.404 | 0.0774 | 1.0 |
| run2 | 0.404 | 0.0774 | 1.0 |
| run3 | 0.404 | 0.0774 | 1.0 |

Repeatability: score changed in 0/20 cases; mean abs change 0.0, max 0.

## Part 4 - 50 confirmed cache misses

| Stage | p50 (ms) | p95 (ms) | % of cache-miss end-to-end |
| --- | --- | --- | --- |
| Cache lookup | 128.1 | 1334.9 | 0.3% |
| Planner | 15100.3 | 30341.4 | 14.6% |
| Writer | 22986.6 | 48560.5 | 24.1% |
| Reviewer | 16758.6 | 25440.7 | 14.8% |
| Queue wait (total) | 53.2 | 1229.1 | 1.1% |
| Evaluation | 49714.8 | 75078.5 | 45.6% |
| End-to-end | 109269.5 | 169244.3 | |

End-to-end = cache_lookup start -> evaluation end, per trace.

Trace examples: cache_miss = 31a611af-e140-4d27-9e17-a5c4ef6a2a7c, cache_hit = 0eefeba3-9061-4adc-81fa-63dcb28536c0, failed = 11b0c62f-4d58-49ab-bcf7-055874b9fc60
