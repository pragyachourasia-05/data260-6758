"""HW9 Part 2 - Q&A endpoint: semantic cache at the ingress, HW8 agent pipeline behind it.

    uvicorn qa_api:app --port 8458      (from backend/, with Kafka, Redis, MySQL, Ollama and the three agents running)

POST /qa  {"question": "..."}  ->  answer, is_cached, similarity, latency_ms
"""
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("HW8_LOG", str(ROOT / "reports" / "hw09" / "raw" / "part2_agents.jsonl"))
sys.path.insert(0, str(ROOT / "kafka_agents"))

from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from send_question import ask  # noqa: E402

from app.semantic_cache import SemanticCache, answer_question  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
cache: SemanticCache | None = None


class Question(BaseModel):
    question: str


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global cache
    cache = SemanticCache(threshold=float(os.getenv("CACHE_THRESHOLD", "0.85")))
    yield


app = FastAPI(title="s6758 listing Q&A", lifespan=lifespan)


def run_agents(question: str, context: str) -> dict | None:
    return asyncio.run(ask(question, context))


@app.get("/health")
def health():
    return {"status": "ok", "threshold": cache.threshold}


@app.post("/qa")
def qa(body: Question):
    return answer_question(cache, body.question, run_agents)
