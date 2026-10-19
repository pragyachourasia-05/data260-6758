# HW6 run guide

SID4 6758 · PORT_BASE 8458 · PREFIX s6758 · SEED 6758 · VERIFY_SEED 266758 · DOMAIN_ID 6 (rental housing listings)

## Part 1 - MongoDB document API

Files (all in the shared `backend/app/` package):

| File | Role |
| --- | --- |
| `mongo_config.py` | server configuration (Mongo URI, database `s6758_doc`, SID values) |
| `mongo_db.py` | PyMongo connection, `listings` collection with `$jsonSchema` validator + index |
| `doc_schemas.py` | Pydantic create / update / output models |
| `routes_listings_doc.py` | CRUD route handlers under `/api/listings` |
| `main.py` | includes the router, CORS middleware, JSON content-type middleware |

Document fields: `title` (required, max 100), `description` (optional), `status` enum
(`available` default / `pending` / `rented`), `property_type` enum (`apartment`, `house`,
`condo`, `studio`, `townhouse`), `monthly_rent` (optional, >= 0), `available_from`
(required date/time), `created_at` / `updated_at` (set automatically).

### 1. Start MongoDB

```powershell
docker compose up -d
docker ps
```

### 2. Start the backend (from the repository root)

```powershell
.\venv\Scripts\activate
pip install pymongo
cd backend
uvicorn app.main:app --port 8458
```

Check `http://localhost:8458/health` shows `"mongo_ok": true`. Swagger UI: `http://localhost:8458/docs`.

### 3. Seed sample data (second terminal, repository root)

```powershell
python backend\seed_hw06.py
```

### 4. CRUD + validation checks (curl.exe in PowerShell, or Swagger "Try it out")

```powershell
curl.exe -s -X POST http://localhost:8458/api/listings -H "Content-Type: application/json" -d "{\"title\":\"1BR in Japantown\",\"property_type\":\"apartment\",\"monthly_rent\":2400,\"available_from\":\"2026-11-10T00:00:00Z\"}"
curl.exe -s http://localhost:8458/api/listings
curl.exe -s http://localhost:8458/api/listings/<id>
curl.exe -s -X PUT http://localhost:8458/api/listings/<id> -H "Content-Type: application/json" -d "{\"status\":\"pending\",\"monthly_rent\":2350}"
curl.exe -s -i -X DELETE http://localhost:8458/api/listings/<id>
curl.exe -s -i http://localhost:8458/api/listings/<id>
```

Expected: 201, 200, 200, 200 (status/rent/updated_at changed), 204, then 404.

Validation (all should be rejected):

```powershell
curl.exe -s -i -X POST http://localhost:8458/api/listings -H "Content-Type: application/json" -d "{\"property_type\":\"apartment\",\"available_from\":\"2026-11-01\"}"
curl.exe -s -i -X POST http://localhost:8458/api/listings -H "Content-Type: application/json" -d "{\"title\":\"x\",\"property_type\":\"castle\",\"available_from\":\"2026-11-01\"}"
curl.exe -s -i -X POST http://localhost:8458/api/listings -H "Content-Type: application/json" -d "{\"title\":\"x\",\"property_type\":\"condo\",\"available_from\":\"next week\",\"monthly_rent\":\"cheap\"}"
curl.exe -s -i -X POST http://localhost:8458/api/listings -H "Content-Type: text/plain" -d "title=x"
curl.exe -s -i http://localhost:8458/api/listings/123
```

Expected: 422 missing `title`, 422 invalid enum, 422 bad date + bad number, 415 non-JSON body, 400 invalid id.

### 5. MongoDB evidence

MongoDB Compass -> connect to `mongodb://localhost:27017` -> database `s6758_doc` -> collection
`listings` (Documents tab), and the Validation tab showing the `$jsonSchema`.

## Part 2 - Short-, long-, and episodic memory

Same database `s6758_doc`, new collections `messages`, `summaries`, `episodes` (each with a
`$jsonSchema` validator). The Part 1 `listings` collection is unchanged.

| File | Role |
| --- | --- |
| `backend/app/memory.py` | memory logic: short-term window, summarization trigger, lifetime condensing, episode extraction, embedding + cosine retrieval, prompt assembly, usage logging |
| `backend/app/routes_memory.py` | `POST /api/chat`, `GET /api/memory/{user_id}`, `GET /api/aggregate/{user_id}` |
| `src/model_client.py` | HW1 model adapter (now accepts extra ChatOllama options: `num_ctx`, `seed`, `format`) |
| `frontend/chat.html` | mini chat page served at `http://localhost:8458/chat` |
| `backend/run_hw06_chat_demo.py` | sends a 12-message session and saves the JSON evidence |

Settings (env vars, defaults in `mongo_config.py`): `SHORT_TERM_N=12`, `SUMMARIZE_EVERY_USER_MSGS=4`,
`LIFETIME_EVERY_SESSION_SUMMARIES=2`, `EPISODIC_TOP_K=3`, model `llama3.2:3b`, `NUM_CTX=8192`.
Embeddings: `EMBED_BACKEND=hash` (local feature-hashing, 512 dims, no extra model). To use a neural
embedding instead: `ollama pull nomic-embed-text` and set `EMBED_BACKEND=ollama`.

### Run

1. MongoDB + backend running as in Part 1 (`ollama` must be running with `llama3.2:3b`).
2. Scripted 12-message session (prints each turn; about 30-60 s per turn on CPU):

```powershell
python backend\run_hw06_chat_demo.py
```

3. Or chat by hand at `http://localhost:8458/chat` (user_id `pragya`).
4. JSON evidence:

```powershell
curl.exe -s http://localhost:8458/api/memory/pragya
curl.exe -s http://localhost:8458/api/aggregate/pragya
```

5. One request by curl (Postman works the same):

```powershell
curl.exe -s -X POST http://localhost:8458/api/chat -H "Content-Type: application/json" -d "{\"user_id\":\"pragya\",\"message\":\"What is my budget?\"}"
```

Compass: `s6758_doc` -> `messages`, `summaries`, `episodes` (Documents tab).

## Part 3 - What memory costs

- `reports/hw06/memory_probes.yaml`: five fixed probes, answer criteria, 1-5 rubric.
- `reports/hw06/cases/conversation_30.yaml`: the fixed 30-message conversation.
- `backend/run_hw06_memory_cost.py`: replays it for SHORT_TERM_N = 4, 12, 30 and the
  `compress_assistant` policy (N = 30), each as a fresh user, asks the probes and scores them.

```powershell
python backend\run_hw06_memory_cost.py --tag run2
```

Outputs in `reports/hw06/raw/`: `part3/<setting>.json`, `part3_turns.csv`, `part3_probe_scores.json`,
`part3_policy_comparison.json`, `part3_summary.json`, `part3_console.txt`. Every `/api/chat`
request is also logged to `chat_usage.jsonl`. Takes about 2 hours on CPU; stop other Docker stacks first.

## Part 4 - File-based memory

| File | Role |
| --- | --- |
| `AGENT.md` | durable agent/project instructions (5 categories + HW1 code-review mode) |
| `MEMORY.md` | durable facts; `<!-- last_consolidated: ... -->` timestamp |
| `src/file_memory.py` | load files, build system prompt, read timestamp, consolidation check, consolidate, `/dream`, `/compact` |
| `code/hw1_client.py` | HW1 CLI + `/memory`, `/compact`, `/dream`, `/help` |
| `tests/test_file_memory.py` | offline tests (14) |
| `code/generate_with_agent_md.py` / `code/check_agent_md_rules.py` | generate one function under AGENT.md, then check it rule by rule |

```powershell
python code\hw1_client.py                     # interactive; type /help
python code\hw1_client.py < reports\hw06\cases\part4_session_a.txt   # scripted /compact run
python -m pytest tests -q
python code\check_agent_md_rules.py
```

Consolidation evidence: `reports/hw06/memory/MEMORY_original.md` (55 lines) ->
`MEMORY_consolidated.md` (36 lines) -> `MEMORY_final_reviewed.md` (after /dream and human review).

## Verification

```powershell
python verify_hw06.py      # or: make verify-hw06
```

## Report screenshots

```powershell
powershell -ExecutionPolicy Bypass -File code\take_hw06_screenshots.ps1          # all 10
powershell -ExecutionPolicy Bypass -File code\take_hw06_screenshots.ps1 -Only 2.1 # redo one
```

Each step prints a banner with the student name and timestamp, runs `code/hw06_screenshot_steps.py <id>`,
and saves the capture to `reports/hw06/screenshots/<id>.png`.
