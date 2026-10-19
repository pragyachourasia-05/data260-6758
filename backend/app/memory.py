"""HW6 Part 2/3: short-term, long-term (summary) and episodic memory for /api/chat.

Flow of one chat turn (see chat_turn):
  1. save the user message to `messages`
  2. load the short-term window (last N messages of the session, before this one)
  3. load the latest session summary and lifetime summary from `summaries`
  4. embed the message and retrieve the top-k episodes by cosine similarity
  5. compose the prompt and call the local model through the HW1 ModelClient
  6. save the reply, extract up to 3 episodic facts, and every M user
     messages refresh the session summary (and periodically the lifetime one)
Every request appends one usage record (tokens per prompt component, latency)
to USAGE_LOG for Part 3.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx
import numpy as np
from pymongo import DESCENDING

from . import mongo_config as cfg
from .mongo_db import get_memory_collections

if str(cfg.ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(cfg.ROOT_DIR))
from src.model_client import ModelClient  # noqa: E402  (HW1 model adapter)

SYSTEM_PRIMER = (
    "You are HomeFinder, a friendly rental-housing assistant for the San Jose / Bay Area. "
    "You help one user plan an apartment search. Any summary or remembered-facts sections "
    "contain things the user told you earlier. When the user asks about something they told "
    "you, answer from those sections or the conversation and quote the exact detail (names, "
    "numbers, dates). Never claim to remember something that is not written there; if the "
    "answer is missing, say you do not know. Keep replies under 80 words."
)

_chat_client: ModelClient | None = None
_json_client: ModelClient | None = None


def chat_client() -> ModelClient:
    global _chat_client
    if _chat_client is None:
        _chat_client = ModelClient(
            model=cfg.OLLAMA_MODEL, base_url=cfg.OLLAMA_URL, temperature=0.0, verbose=False,
            num_ctx=cfg.NUM_CTX, seed=cfg.SEED, num_predict=200,
        )
    return _chat_client


def json_client() -> ModelClient:
    global _json_client
    if _json_client is None:
        _json_client = ModelClient(
            model=cfg.OLLAMA_MODEL, base_url=cfg.OLLAMA_URL, temperature=0.0, verbose=False,
            num_ctx=cfg.NUM_CTX, seed=cfg.SEED, num_predict=300, format="json",
        )
    return _json_client


def now() -> datetime:
    return datetime.now(timezone.utc)


def estimate_tokens(text: str) -> int:
    """Rough Llama-3 token estimate (~4 characters per token).

    Only used to split the prompt into components; the total prompt size
    always comes from Ollama's real prompt_eval_count.
    """
    return math.ceil(len(text) / 4) if text else 0


# ---------------------------------------------------------------------------
# Embeddings + retrieval
# ---------------------------------------------------------------------------
_STOP = {
    "the", "and", "for", "that", "with", "this", "from", "into", "your", "you", "are", "was",
    "were", "have", "has", "had", "about", "how", "can", "will", "what", "when", "where",
    "which", "who", "is", "it", "as", "an", "a", "of", "to", "in", "on", "my", "me", "i",
    "do", "does", "did", "be", "am", "so", "or", "at", "by", "we", "our", "us", "please",
    "tell", "remind", "again", "also", "just", "would", "like", "want", "need", "user",
}


def _stem(word: str) -> str:
    """Light suffix stripping so "drives"/"drive" and "visits"/"visit" share a feature.

    (The first version stripped "es" before "s", which turned "drives" into "driv"
    and broke matching against "drive"; see reports/hw06/raw/part3_run1_aborted.)
    """
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("sses", "ches", "shes", "xes")):
        return word[:-2]
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        word = word[:-1]
    return word.rstrip("e") if len(word) > 4 else word


def _hash_embed(text: str, dim: int) -> list[float]:
    """Feature-hashing embedding: stemmed unigrams + bigrams + char trigrams.

    Deterministic and dependency-free, so retrieval is reproducible across runs.
    """
    vec = np.zeros(dim, dtype=np.float64)
    words = [_stem(w) for w in re.findall(r"[a-z0-9$]+", text.lower()) if w not in _STOP]
    features: list[tuple[str, float]] = [(w, 1.0) for w in words]
    features += [(f"{a}_{b}", 0.7) for a, b in zip(words, words[1:])]
    for w in words:
        padded = f"#{w}#"
        features += [(padded[i:i + 3], 0.25) for i in range(len(padded) - 2)]
    for feat, weight in features:
        h = int(hashlib.md5(feat.encode()).hexdigest(), 16)
        sign = 1.0 if (h >> 1) & 1 else -1.0
        vec[h % dim] += sign * weight
    norm = np.linalg.norm(vec)
    return (vec / norm).tolist() if norm else vec.tolist()


def embed(text: str) -> list[float]:
    if cfg.EMBED_BACKEND == "ollama":
        resp = httpx.post(f"{cfg.OLLAMA_URL}/api/embed", json={"model": cfg.EMBED_MODEL, "input": text}, timeout=60)
        resp.raise_for_status()
        return [float(x) for x in resp.json()["embeddings"][0]]
    return _hash_embed(text, cfg.EMBED_DIM)


def cosine(a, b) -> float:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / denom) if denom else 0.0


def retrieve_episodes(user_id: str, query_embedding: list[float], k: int) -> list[dict]:
    """Top-k episodes for this user by cosine similarity to the current message."""
    _, _, episodes = get_memory_collections()
    scored = []
    for ep in episodes.find({"user_id": user_id}, {"fact": 1, "importance": 1, "embedding": 1, "created_at": 1}):
        scored.append({
            "fact": ep["fact"],
            "importance": ep["importance"],
            "score": round(cosine(query_embedding, ep["embedding"]), 4),
        })
    scored.sort(key=lambda e: (e["score"], e["importance"]), reverse=True)
    return [e for e in scored[:k] if e["score"] > 0]


# ---------------------------------------------------------------------------
# Messages + summaries
# ---------------------------------------------------------------------------
def save_message(user_id: str, session_id: str, role: str, content: str):
    messages, _, _ = get_memory_collections()
    return messages.insert_one({
        "user_id": user_id, "session_id": session_id, "role": role,
        "content": content, "created_at": now(),
    }).inserted_id


def load_short_term(user_id: str, session_id: str, n: int, exclude_id=None) -> list[dict]:
    """Sliding window: the last n messages of the session, oldest first."""
    if n <= 0:
        return []
    messages, _, _ = get_memory_collections()
    query = {"user_id": user_id, "session_id": session_id}
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    docs = list(messages.find(query, {"role": 1, "content": 1}).sort([("created_at", DESCENDING), ("_id", DESCENDING)]).limit(n))
    return [{"role": d["role"], "content": d["content"]} for d in reversed(docs)]


def latest_summary(user_id: str, scope: str, session_id: str | None = None) -> dict | None:
    _, summaries, _ = get_memory_collections()
    query = {"user_id": user_id, "scope": scope}
    query["session_id"] = session_id if scope == "session" else None
    return summaries.find_one(query, sort=[("created_at", DESCENDING), ("_id", DESCENDING)])


def _transcript(msgs: list[dict]) -> str:
    return "\n".join(f"{m['role']}: {m['content']}" for m in msgs)


def summarize_session(user_id: str, session_id: str) -> dict:
    """Fold recent messages into the session summary (concise bullets)."""
    messages, summaries, _ = get_memory_collections()
    previous = latest_summary(user_id, "session", session_id)
    since = {"user_id": user_id, "session_id": session_id}
    if previous:
        since["created_at"] = {"$gt": previous["created_at"]}
    recent = list(messages.find(since).sort("created_at", 1))
    prompt = (
        "Update the running summary of a conversation between a renter (user) and an assistant.\n"
        f"Previous summary:\n{previous['text'] if previous else '(none)'}\n\n"
        f"New messages:\n{_transcript(recent)}\n\n"
        "Write at most 8 short bullet points ('- ' prefix) with the user's concrete facts and "
        "preferences (names, numbers, dates, places). If a newer message changes an earlier fact, "
        "keep only the newer value. Do not include the assistant's suggestions. Output only the bullets."
    )
    result = chat_client().complete([{"role": "user", "content": prompt}])
    text = result["text"].strip()
    summaries.insert_one({
        "user_id": user_id, "session_id": session_id, "scope": "session",
        "text": text, "created_at": now(),
    })
    return result


def condense_lifetime(user_id: str) -> dict:
    """Condense the latest summary of each session plus the old lifetime summary."""
    _, summaries, _ = get_memory_collections()
    latest_per_session = list(summaries.aggregate([
        {"$match": {"user_id": user_id, "scope": "session"}},
        {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$session_id", "text": {"$first": "$text"}, "created_at": {"$first": "$created_at"}}},
        {"$sort": {"created_at": -1}},
        {"$limit": 5},
    ]))
    previous = latest_summary(user_id, "user")
    joined = "\n\n".join(f"Session {s['_id']}:\n{s['text']}" for s in reversed(latest_per_session))
    prompt = (
        "Condense these session summaries into one lifetime profile of the user.\n"
        f"Previous lifetime summary:\n{previous['text'] if previous else '(none)'}\n\n"
        f"Session summaries:\n{joined}\n\n"
        "Write at most 8 bullet points ('- ' prefix) of durable facts and preferences. "
        "Newer sessions override older facts. Output only the bullets."
    )
    result = chat_client().complete([{"role": "user", "content": prompt}])
    summaries.insert_one({
        "user_id": user_id, "session_id": None, "scope": "user",
        "text": result["text"].strip(), "created_at": now(),
    })
    return result


def maybe_summarize(user_id: str, session_id: str) -> dict:
    """Summarization trigger: every SUMMARIZE_EVERY_USER_MSGS user messages."""
    messages, summaries, _ = get_memory_collections()
    user_count = messages.count_documents({"user_id": user_id, "session_id": session_id, "role": "user"})
    info = {"session_summary": False, "lifetime_summary": False, "input_tokens": 0, "output_tokens": 0}
    if user_count == 0 or user_count % cfg.SUMMARIZE_EVERY_USER_MSGS:
        return info
    r = summarize_session(user_id, session_id)
    info.update(session_summary=True, input_tokens=r["input_tokens"], output_tokens=r["output_tokens"])
    n_session_summaries = summaries.count_documents({"user_id": user_id, "scope": "session"})
    if n_session_summaries % cfg.LIFETIME_EVERY_SESSION_SUMMARIES == 0:
        r = condense_lifetime(user_id)
        info["lifetime_summary"] = True
        info["input_tokens"] += r["input_tokens"]
        info["output_tokens"] += r["output_tokens"]
    return info


# ---------------------------------------------------------------------------
# Episodic extraction
# ---------------------------------------------------------------------------
def extract_episodes(user_id: str, session_id: str, message: str) -> dict:
    """Extract up to 3 short facts (with importance 0..1), embed and store them."""
    _, _, episodes = get_memory_collections()
    prompt = (
        "Extract durable personal facts the USER states about themselves in this message "
        "(e.g. name, budget, move-in date, pets, workplace, must-haves, deal-breakers).\n"
        f"Message: \"{message}\"\n\n"
        'Return JSON: {"facts": [{"fact": "<one short sentence, third person>", "importance": <0..1>}]}. '
        "At most 3 facts. Questions, greetings and small talk have no facts: return {\"facts\": []}."
    )
    result = json_client().complete([{"role": "user", "content": prompt}])
    stored, skipped = [], 0
    try:
        facts = json.loads(result["text"]).get("facts", [])
    except (json.JSONDecodeError, AttributeError):
        facts = []
    existing = list(episodes.find({"user_id": user_id}, {"embedding": 1}))
    for item in facts[: cfg.MAX_FACTS_PER_MESSAGE]:
        if not isinstance(item, dict):
            continue
        fact = str(item.get("fact", "")).strip()[:300]
        if not fact:
            continue
        try:
            importance = min(1.0, max(0.0, float(item.get("importance", 0.5))))
        except (TypeError, ValueError):
            importance = 0.5
        emb = embed(fact)
        if any(cosine(emb, e["embedding"]) > 0.95 for e in existing):
            skipped += 1  # near-duplicate of a stored episode
            continue
        episodes.insert_one({
            "user_id": user_id, "session_id": session_id, "fact": fact,
            "importance": importance, "embedding": emb, "created_at": now(),
        })
        existing.append({"embedding": emb})
        stored.append({"fact": fact, "importance": importance})
    return {"stored": stored, "duplicates_skipped": skipped,
            "input_tokens": result["input_tokens"], "output_tokens": result["output_tokens"]}


# ---------------------------------------------------------------------------
# Memory-saving policy (Part 3.4)
# ---------------------------------------------------------------------------
def _first_sentence(text: str, max_words: int = 25) -> str:
    sentence = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    words = sentence.split()
    return " ".join(words[:max_words]) + (" ..." if len(words) > max_words else "")


def apply_policy(window: list[dict], policy: str) -> list[dict]:
    """compress_assistant: keep user turns verbatim, shrink older assistant turns.

    Facts live in the user's messages; the assistant's long replies are mostly
    restatements, so all but the last two window messages are cut to their
    first sentence (<= 25 words).
    """
    if policy != "compress_assistant":
        return window
    out = []
    for i, m in enumerate(window):
        if m["role"] == "assistant" and i < len(window) - 2:
            out.append({"role": "assistant", "content": _first_sentence(m["content"])})
        else:
            out.append(m)
    return out


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------
def build_prompt(message: str, window: list[dict], session_summary: str | None,
                 lifetime_summary: str | None, facts: list[dict]) -> tuple[list[dict], dict]:
    """system primer + long-term summaries + short-term window + current message + episodic facts."""
    long_term = ""
    if lifetime_summary:
        long_term += f"\n\nLifetime summary of this user:\n{lifetime_summary}"
    if session_summary:
        long_term += f"\n\nSummary of this session so far:\n{session_summary}"
    episodic = ""
    if facts:
        episodic = "\n\n[Relevant facts remembered about the user]\n" + "\n".join(f"- {f['fact']}" for f in facts)

    msgs = [{"role": "system", "content": SYSTEM_PRIMER + long_term}]
    msgs += window
    msgs.append({"role": "user", "content": message + episodic})

    components = {
        "system_primer": estimate_tokens(SYSTEM_PRIMER),
        "long_term_summary": estimate_tokens(long_term),
        "short_term_window": sum(estimate_tokens(m["content"]) for m in window),
        "current_message": estimate_tokens(message),
        "episodic_facts": estimate_tokens(episodic),
    }
    return msgs, components


def chat_turn(user_id: str, message: str, session_id: str | None = None,
              short_term_n: int | None = None, policy: str | None = None) -> dict:
    t0 = time.perf_counter()
    session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"
    n = cfg.SHORT_TERM_N if short_term_n is None else short_term_n
    policy = policy or "none"

    msg_id = save_message(user_id, session_id, "user", message)
    window = apply_policy(load_short_term(user_id, session_id, n, exclude_id=msg_id), policy)
    session_summary = latest_summary(user_id, "session", session_id)
    lifetime_summary = latest_summary(user_id, "user")
    facts = retrieve_episodes(user_id, embed(message), cfg.EPISODIC_TOP_K)

    prompt, components = build_prompt(
        message, window,
        session_summary["text"] if session_summary else None,
        lifetime_summary["text"] if lifetime_summary else None,
        facts,
    )
    t_model = time.perf_counter()
    result = chat_client().complete(prompt)
    model_ms = (time.perf_counter() - t_model) * 1000
    reply = result["text"].strip()
    save_message(user_id, session_id, "assistant", reply)

    t_ep = time.perf_counter()
    extraction = extract_episodes(user_id, session_id, message)
    extraction_ms = (time.perf_counter() - t_ep) * 1000
    t_sum = time.perf_counter()
    summary_info = maybe_summarize(user_id, session_id)
    summary_ms = (time.perf_counter() - t_sum) * 1000
    total_ms = (time.perf_counter() - t0) * 1000

    usage = {
        "ts": now().isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "short_term_n": n,
        "policy": policy,
        "prompt_tokens": result["input_tokens"],
        "completion_tokens": result["output_tokens"],
        "cached_prompt_tokens": result.get("cached_input_tokens", 0),
        "component_tokens_est": components,
        "template_overhead_tokens": result["input_tokens"] - sum(components.values()),
        "memory_maintenance_tokens": {
            "input": extraction["input_tokens"] + summary_info["input_tokens"],
            "output": extraction["output_tokens"] + summary_info["output_tokens"],
        },
        "latency_ms": round(total_ms, 1),
        "model_latency_ms": round(model_ms, 1),
        "extraction_ms": round(extraction_ms, 1),
        "summarization_ms": round(summary_ms, 1),
        "summary_triggered": summary_info["session_summary"],
        "lifetime_triggered": summary_info["lifetime_summary"],
    }
    cfg.USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with cfg.USAGE_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(usage) + "\n")

    return {
        "user_id": user_id,
        "session_id": session_id,
        "reply": reply,
        "memory_used": {
            "short_term_count": len(window),
            "short_term": window,
            "long_term_summary": {
                "session": session_summary["text"] if session_summary else None,
                "lifetime": lifetime_summary["text"] if lifetime_summary else None,
            },
            "episodic_facts": facts,
            "new_episodes": extraction["stored"],
            "summary_triggered": summary_info["session_summary"],
            "lifetime_triggered": summary_info["lifetime_summary"],
        },
        "usage": usage,
    }
