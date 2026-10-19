# AI use - HW6

## 1. What I used an AI assistant for, and what I did myself

I used Claude Code as a coding assistant for most of the implementation in this homework. I gave
it the HW6 brief, the two class demos (the FastAPI + PyMongo study planner and the long-term-memory
demo) and my HW1-HW5 repository, and used it to plan the work part by part and to write most of
the code: the MongoDB listings API (config, connection, schemas and routes in separate files), the
memory module behind `/api/chat`, the Part 3 experiment runner and probe scorer, the file-based
memory functions and CLI commands, the tests, the verification script, and the layout of this report.

What I did myself: I kept the rental-listings domain from my earlier homeworks and asked for the work
to be done one part at a time so I could check and push each part. I set up and ran everything on my
own laptop (Docker with MongoDB, the FastAPI backend on port 8458, Ollama with llama3.2:3b), used the
chat page myself, ran the demo session and the memory experiments, took the screenshots, and checked
the outputs against the requirements in the brief. I decided what to keep when results looked wrong,
read the results to understand what the memory settings change, and handled Git (branch, commits, tag).

## 2. Something the AI produced that was wrong

Three things the assistant wrote were wrong, and each was caught by a test or a check:

- **Embedding stemmer.** The first version of `_stem()` removed "es" before "s", so "drives" became
  "driv" while "drive" stayed "drive". The stored fact "Pragya drives a Tesla Model 3" only scored
  0.02 against the probe "What kind of car do I drive?", so that fact was not retrieved.
- **Function generated under AGENT.md.** I had llama3.2:3b generate `parse_monthly_rent` with AGENT.md
  as its instructions. It followed all the style rules (snake_case, type hints, docstring, ValueError,
  no print) but failed its own first example: `"$2,400/mo"` raised a ValueError because the comma and
  "/mo" were never removed. One of its tests was also wrong (it expected `"$2,400"` to be rejected).
- **Memory consolidation and `/dream`.** Consolidating an already-consolidated MEMORY.md lost the
  "(seen Nx)" counts and the "Needs review" flags, and `/dream` saved my correction under a new key
  (`hw6_project_database`) instead of `mongo_db`, so the wrong value was never replaced.

## 3. How the problems were found

- The stemmer bug showed up in the Part 3 results: at N=4 the car probe scored 1/5. The episodic facts
  retrieved for that probe (saved in `raw/part3_run1_aborted/n4.json`) and their cosine scores showed
  the 0.02 score and the "driv" / "drive" mismatch.
- `code/check_agent_md_rules.py` checks each AGENT.md rule separately and also runs the tests. It
  reported 9/10 for the generated function, with "tests pass offline: 1 failed"
  (`raw/agent_md_generated_v1/agent_md_check.json`).
- The consolidation bug was caught by the test `test_consolidation_is_idempotent_and_keeps_history`,
  and the `/dream` problem is visible in the session output `raw/part4_dream_session_before_fix.txt`.

## 4. What was changed and why it works now

- The stemmer now handles "ies"/"sses"/"ches"/"xes" first and then strips one trailing "s", "ing" or
  "ed" and a final "e", so "drive", "drives" and "driving" share one stem (the score went from 0.02 to
  0.16). Because this changes retrieval, I reran the whole Part 3 sweep so every setting uses the same
  code. The first run is kept in `raw/part3_run1_aborted/`; it also stopped when MongoDB timed out
  because other Docker containers on my laptop were using all the memory.
- The generated function was rewritten with one regular expression (optional sign, "$", digits with
  commas or decimals, optional "k"), and the wrong test was fixed. The checker now reports 10/10 and
  all tests pass. What I learned: AGENT.md controls how generated code looks, but only tests show
  whether it actually works.
- Consolidation now reads "(seen Nx)" back as a count, keeps earlier "Needs review" lines until that
  key is decided again, and `/dream` is given the existing keys and told to reuse them. 14 offline
  tests cover these cases. The one wrong resolution left (`mongo_db`) I fixed through a recorded human
  review in MEMORY.md, which is exactly what the "Needs review" section is for.
