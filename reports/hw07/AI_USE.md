# AI use - HW7

## 1. What I used AI for and what I did myself

I used Claude and ChatGPT to debug my problems and understand the coding parts. I gave it the HW7 brief and
used it to help write the users-table migration and JWT/role code, the agent loop and repair path, the
Reflexion verifier and retry loop, the bike-share tools, agent and UI page, the attack tests, the file tools and
safety gate, the verification scripts and the report layout.

I chose to keep my rental-listings domain and the existing `/listings` routes, chose the multi-month rider
design for the bike-share scenarios, ran everything on my laptop (MySQL and MongoDB in Docker, Ollama, backend
on port 8458), checked the outputs and screenshots against the brief, and did the Git work.

## 2. Something the AI got wrong

- The first safety gate allowed five unsafe commands. It only checked the first command, allowed `python -c`,
  and missed `find -exec rm` and `sudo` inside backticks.
- The first reliability summary used a wrong formula and showed 0% after repair, even though most runs finished
  correctly.
- The verifier rejected a correct answer ("cheaper by $600") because $600 does not appear in any tool result.

## 3. How I found the problems

- The gate passed the ten required commands, so I tried extra chained and piped commands and five got through.
- 0% after repair did not match the logs, so I checked the metric against the per-attempt results.
- I checked all 11 Part 3 rejections by hand and found one correct answer.

## 4. What I changed

- Gate v2 checks every chained or piped part, blocks command substitution, removes `python -c` and adds the
  missing patterns. All five commands are now blocked and the gate test is 10/10.
- I fixed the reliability formula and re-ran the 21 attempts.
- I kept the false rejection in the report. The fix would be to accept simple arithmetic on observed numbers.
