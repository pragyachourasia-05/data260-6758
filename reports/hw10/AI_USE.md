# AI use - HW10

## 1. What I used AI for and what I did myself

I used Claude to debug problems and understand the evaluation, tracing and Streamlit parts. I gave it the HW10 brief and the demo files and used it to help write the span tracing, the evaluator and judge setup, the latency experiment, the dashboard, the verify script and the report layout.

I labeled the 20 drafts in human_labels.csv myself, without AI, and they were committed before the judge ran. I ran everything on my laptop (Docker, Kafka, Redis, MySQL and Ollama), checked the outputs and screenshots against the brief, and did the final Git push and tag myself.

## 2. Something the AI got wrong

- The first failed-trace test did not fail. The fail flag was on the inbox message, but the Planner builds a new message for the Writer, so the flag was dropped and the request finished normally.
- The span file had 4 broken lines out of 581. Several processes appended to the same file at the same time, and on Windows that is not atomic.
- The 1-5 conversion used Python's round(), which rounds 2.5 down to 2.
- A second try at the failed trace used "rent at 138 Research Avenue, is it a house?". This was a cache hit on the earlier "rent at 139" question at 0.972, the same false-hit problem as in HW9.

## 3. How the problems were found

- Reading the spans for the "failed" trace: every stage was ok and the Writer log had no error.
- The trace viewer crashed on a line that was not valid JSON.
- Checking a judge score of 0.25 by hand.
- The failed-trace run printed is_cached=True.

## 4. What was changed

- The agent loop now copies the fail flag onto the next message, and the failed example was run again with a question that is not in the cache.
- write_span now locks the file before appending. A test with 4 processes writing 1,200 lines gave 0 broken lines. The 4 old broken lines were kept and are skipped when the file is read. All of them were evaluator-side queue spans, which are not used in the latency table.
- Halves now round up (2.5 -> 3).
