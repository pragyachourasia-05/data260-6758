# Agent Instructions

Durable instructions for any agent working in this repository (data260-6758).
Facts learned from conversations live in MEMORY.md, not here.

## Project description
- This repository is a rental-housing listings application for DATA-260: a FastAPI backend on port 8458, a React frontend, MySQL database `s6758_rel`, MongoDB database `s6758_doc`, and a local-model assistant with short-term, long-term and episodic memory.
- Shared code lives in root-level folders (`backend/`, `frontend/`, `src/`, `rag/`); every homework extends these folders instead of copying them.

## Technology stack
- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy (MySQL) and PyMongo (MongoDB).
- All model calls go through `src/model_client.ModelClient` to the local Ollama model `llama3.2:3b`; no hosted or paid LLM APIs.

## Coding conventions
- Function names use snake_case; every parameter and the return value have type hints; every public function has a docstring.
- Validate inputs explicitly and raise `ValueError` with a clear message for bad input; never fail silently or return a magic value.
- Library code does not call `print()`; it returns values and lets the caller decide what to show.
- Configuration comes from environment variables or `backend/.env`; never hard-code passwords, API keys or tokens.

## Testing approach
- Every new function gets pytest tests in a `test_*.py` file: at least one normal case and one invalid input that must raise.
- Tests run offline: no network, database or model calls.

## Prohibited actions
- Never commit `.env` files, credentials, or the `venv/` folder.
- Never delete or overwrite MongoDB/MySQL data outside a test or an explicit user request.
- Never invent listings, prices, addresses or owner contact details.

## Code review mode (from HW1)
When the user asks you to review code, review it for correctness, bugs, security concerns, missing tests and maintainability issues, and follow these output rules:
- Your response must contain bullet points only; every line must begin with "- ".
- Do not write paragraphs, headings, introductions, or conclusions.
- If you find no issues, respond exactly: "- No issues found."
