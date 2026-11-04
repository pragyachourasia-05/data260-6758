# HW9 Metrics

## Part 1 - Counter

Redis `s6758:views:listing:4` = 25, MySQL view_count = 20 (last sync at 20).

## Part 2 - Semantic cache, threshold 0.85

| Queries | Hits | Hit rate | Avg latency cached (ms) | Avg latency not cached (ms) |
| --- | --- | --- | --- | --- |
| 12 | 7 | 58% | 47.0 | 43952.0 |

## Part 3 - Threshold sweep (40 cases)

Cost per 40 queries = misses x $0.01 + false hits x $2.00.

| Threshold | Hit rate | False-hit rate | Mean latency (ms) | Total cost |
| --- | --- | --- | --- | --- |
| 0.75 | 75.0% | 35.0% | 15785.5 | $28.10 |
| 0.80 | 75.0% | 30.0% | 15731.8 | $24.10 |
| 0.85 | 70.0% | 25.0% | 18526.9 | $20.12 |
| 0.90 | 52.5% | 12.5% | 26725.2 | $10.19 |
| 0.95 | 35.0% | 5.0% | 34889.8 | $4.26 |

Stale test: rent $1800/month -> $1999/month; version check off served the old rent (True); version check on dropped it and regenerated (True).

## Part 4 - Validation of candidate lessons

| Lesson | Pattern | First-attempt passes before | After | Fixed | Regressions | Kept |
| --- | --- | --- | --- | --- | --- | --- |
| lesson_001 | added_detail | 15 | 16 | val_01 | - | True |

## Part 4 - Test set results

| Variant | Correct | Incorrect | Average attempts | Average latency (ms) |
| --- | --- | --- | --- | --- |
| Baseline | 17 | 1 | 1.0 | 4561.6 |
| Evaluator Repair | 18 | 0 | 1.06 | 4777.4 |
| Lesson Memory | 17 | 1 | 1.11 | 4964.9 |
| Validated Improvement | 18 | 0 | 1.06 | 4464.8 |

Lesson reuse demo: `lesson_001` loaded on: What type of property is 101 Research Avenue?
