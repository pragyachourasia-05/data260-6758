"""HW6 Part 2 endpoints: POST /api/chat, GET /api/memory/{user_id}, GET /api/aggregate/{user_id}."""
import httpx
from fastapi import APIRouter, HTTPException
from pymongo import DESCENDING
from pymongo.errors import PyMongoError

from . import memory
from .doc_schemas import ChatRequest, ChatResponse
from .mongo_db import get_memory_collections

router = APIRouter(prefix="/api", tags=["HW6 Chat memory"])


def _clean(doc: dict | None, drop: tuple = ()) -> dict | None:
    if doc is None:
        return None
    out = {k: v for k, v in doc.items() if k not in drop and k != "_id"}
    out["id"] = str(doc["_id"])
    return out


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        return memory.chat_turn(req.user_id, req.message, req.session_id, req.short_term_n, req.policy)
    except PyMongoError:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.")
    except (httpx.HTTPError, ConnectionError) as exc:
        raise HTTPException(status_code=502, detail=f"Local model (Ollama) call failed: {exc}")


@router.get("/memory/{user_id}")
def get_memory(user_id: str):
    try:
        messages, summaries, episodes = get_memory_collections()
        recent = list(messages.find({"user_id": user_id}).sort([("created_at", DESCENDING), ("_id", DESCENDING)]).limit(16))
        session_summary = summaries.find_one({"user_id": user_id, "scope": "session"}, sort=[("created_at", DESCENDING)])
        lifetime = summaries.find_one({"user_id": user_id, "scope": "user"}, sort=[("created_at", DESCENDING)])
        facts = list(episodes.find({"user_id": user_id}, {"embedding": 0}).sort("created_at", DESCENDING).limit(20))
    except PyMongoError:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.")
    if not recent and not facts:
        raise HTTPException(status_code=404, detail=f"No memory stored for user '{user_id}'.")
    return {
        "user_id": user_id,
        "recent_messages": [_clean(m) for m in reversed(recent)],
        "latest_session_summary": _clean(session_summary),
        "latest_lifetime_summary": _clean(lifetime),
        "episodic_facts": [_clean(f) for f in facts],
    }


@router.get("/aggregate/{user_id}")
def aggregate(user_id: str):
    try:
        messages, summaries, _ = get_memory_collections()
        daily = list(messages.aggregate([
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at", "timezone": "America/Los_Angeles"}},
                "total": {"$sum": 1},
                "user_messages": {"$sum": {"$cond": [{"$eq": ["$role", "user"]}, 1, 0]}},
                "assistant_messages": {"$sum": {"$cond": [{"$eq": ["$role", "assistant"]}, 1, 0]}},
            }},
            {"$sort": {"_id": 1}},
        ]))
        recent_summaries = list(summaries.find({"user_id": user_id}).sort("created_at", DESCENDING).limit(5))
    except PyMongoError:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.")
    return {
        "user_id": user_id,
        "daily_message_counts": [{"date": d.pop("_id"), **d} for d in daily],
        "recent_summaries": [_clean(s) for s in recent_summaries],
    }
