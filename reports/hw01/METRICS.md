\# Assignment Metrics



\## Part 3: Non-Determinism



The same rental listing input was used for all 40 runs.



| Metric | Temperature 0.7 | Temperature 0.0 |

|---|---:|---:|

| Runs | 20 | 20 |

| Distinct tag sets | 15 | 2 |

| Distinct summaries | 17 | 1 |

| Tags in all 20 runs | None | None |

| Tags appearing exactly once | 13 | None |

| Latency p50 | 25,517 ms | 23,508 ms |

| Latency p95 | 37,498 ms | 26,898 ms |

| Latency p99 | 37,498 ms | 26,898 ms |



The dominant temperature-0.0 tag set appeared in 18 of 20 runs. The other tag set appeared twice and differed mainly in wording and capitalization.



At temperature 0.7, two users submitting identical input could receive noticeably different tags and summaries. This variation is acceptable for brainstorming or recommendation tasks, where multiple valid phrasings are useful. It is not acceptable for compliance labels, billing categories, medical classifications, or other tasks requiring repeatable decisions.



The latency values represent the measured Planner and Reviewer model-call times printed by the script.



\## Part 4: Token Accounting



After five conversation turns:



\- Cumulative input tokens: 1,707

\- Cumulative output tokens: 421

\- Cumulative total tokens: 2,128

\- Serialized conversation-history length: 2,988 characters



The prior conversation is resent on every turn because the model does not automatically retain conversation state. Input tokens grow because each new request includes the earlier messages. Growth is eventually limited by the model's context window, after which older history must be summarized, truncated, or removed.

