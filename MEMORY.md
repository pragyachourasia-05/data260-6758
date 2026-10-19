<!-- last_consolidated: 2026-10-19T06:36:32+00:00 -->
# MEMORY
<!-- Durable facts. Format: - [YYYY-MM-DD] key: value. Consolidated by src/file_memory.py -->
## User
- [2026-09-19] name: Pragya Chourasia (seen 2x)
- [2026-10-18] budget: $2,800 per month
- [2026-09-30] cat_name: Miso (seen 3x)
- [2026-09-20] move_in_date: December 1, 2026 (seen 2x)
- [2026-09-04] commute: Sunnyvale internship on Tuesdays and Thursdays
- [2026-09-05] preferred_unit: 1-bedroom or large studio
- [2026-09-18] avoid: ground floor units (seen 2x)
- [2026-09-22] sister_visits: Riya visits monthly, wants room for a sofa bed
- [2026-10-04] car: Tesla Model 3, needs EV charging (seen 2x)
- [2026-10-07] laundry: In-unit laundry required (seen 2x)
## Project
- [2026-08-28] repo: data260-6758
- [2026-09-01] sid4: 6758 (seen 2x)
- [2026-09-12] backend_port: 8458 (seen 2x)
- [2026-09-14] frontend: React + Vite on port 5173 (seen 2x)
- [2026-09-01] relational_db: MySQL s6758_rel on port 3307
- [2026-09-26] domain: Rental housing listings (seen 2x)
- [2026-10-08] collaborators: Sbnikitha, supriyaselvanganesan (seen 2x)
- [2026-10-18] mongo_db: s6758_doc
## Environment
- [2026-10-03] preferred_model: llama3.2:3b (seen 2x)
- [2026-10-09] ollama_url: http://localhost:11434 (seen 3x)
- [2026-09-08] os: Windows 11 with PowerShell and Git Bash (seen 2x)
- [2026-10-04] hardware: Intel i5-1335U, 16 GB RAM, no GPU (seen 2x)
## Resolved contradictions
- budget: kept "$2,700 per month" (2026-10-11) over "$2,400 per month" (2026-09-02) - newest value
- cat_name: kept "Miso" (2026-09-30) over "Mochi? (maybe misheard)" (2026-10-12) - newer value is hedged/uncertain, kept newest confident value
- backend_port: kept "8458" (2026-09-12) over "8000" (2026-08-28) - newest value
- mongo_db: kept "study_planner_demo" (2026-10-18) over "s6758_doc" (2026-10-17) - newest value
- preferred_model: kept "llama3.2:3b" (2026-10-03) over "qwen3:8b" (2026-09-05) - newest value
- budget: kept "$2,800 per month" (2026-10-18) over "$2,700 per month" (2026-10-11) - newest value
- mongo_db: human review restored "s6758_doc" over "study_planner_demo" (2026-10-18) - the recency choice was wrong (study_planner_demo is the class demo)
- budget: human review confirmed "$2,800 per month" (2026-10-18) - the "Needs review" flag was a false positive (a real raise)
