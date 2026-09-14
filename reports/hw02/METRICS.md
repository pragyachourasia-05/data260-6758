\# DATA-260 Homework 2 Metrics



\## Configuration



\- SID4: 6758

\- Domain: Rental housing listings

\- Model: llama3.2:3b

\- Base URL: http://localhost:11434

\- Temperature: 0.0

\- Frozen input: `reports/hw02/cases/schema\_input.json`

\- Default validation ceiling: 3



\## Part 4b: Schema-validation retry experiment



Thirty runs were executed using the same frozen input and model configuration.



| Outcome | Count |

|---|---:|

| Valid first attempt | 0 |

| Valid after one retry | 0 |

| Valid after two or more retries | 0 |

| Abandoned at ceiling | 30 |

| Total runs | 30 |



\- Mean latency: \*\*42,050.6 ms\*\*

\- Minimum latency: \*\*38,263 ms\*\*

\- Maximum latency: \*\*58,045 ms\*\*



All runs reached the ceiling because the Planner repeatedly generated tags longer than the 30-character schema limit.



\## Part 4c: Ceiling comparison



| Validation ceiling | Runs | Completed | Completion rate | Mean latency |

|---:|---:|---:|---:|---:|

| 2 | 20 | 0 | 0% | 25,051.9 ms |

| 10 | 20 | 20 | 100% | 69,741.7 ms |



The selected deployment ceiling is \*\*10\*\* because it completed all 20 comparison runs. The tradeoff is higher latency.



\## Part 4d: Adversarial input



The adversarial input instructed the model to produce long tags exceeding the schema limit.



| Outcome | Count |

|---|---:|

| Valid runs | 0 |

| Abandoned at ceiling | 5 |

| Total runs | 5 |

| Abandonment rate | 100% |



\- Mean latency: \*\*40,671.8 ms\*\*

\- Minimum latency: \*\*37,647 ms\*\*

\- Maximum latency: \*\*49,670 ms\*\*



The input caused trouble because it directly conflicted with the schema requirement that every tag contain no more than 30 characters. A possible fix is to add deterministic tag truncation or a preprocessing validator that shortens tags before sending them to the schema validator.

