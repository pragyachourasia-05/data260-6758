"""HW9 Parts 2-3 - semantic response cache in Redis, in front of the HW8 agent pipeline.

Each entry holds the query, its embedding, the final answer and a data-version marker. Cosine similarity comes
from a RediSearch vector index. All Redis keys start with s6758.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import time
import uuid

import numpy as np
import redis
from redis.commands.search.field import TagField, TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from sqlalchemy import text

from app.database import engine

logger = logging.getLogger("semantic_cache")
PREFIX = "s6758"
INDEX = f"{PREFIX}:idx:semantic"
ENTRY_PREFIX = f"{PREFIX}:semcache:"
MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DIM = 384
NO_RECORD = "none"
ADDRESS_RE = re.compile(r"\b(\d+)\s+Research\s+(?:Avenue|Ave)\b", re.I)


def find_listing(question: str) -> dict | None:
    """The s6758_rel listing a question names by street address, if any."""
    match = ADDRESS_RE.search(question)
    if not match:
        return None
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, property_address, monthly_rent, property_category, available_units "
                                "FROM listings WHERE property_address LIKE :a ORDER BY id LIMIT 1"),
                           {"a": f"{match.group(1)} Research Avenue%"}).mappings().first()
    return dict(row) if row else None


def listing_context(row: dict | None) -> str:
    if not row:
        return ""
    return (f"Address: {row['property_address']}. Monthly rent: {row['monthly_rent']}. "
            f"Property type: {row['property_category']}. Available units: {row['available_units']}.")


def data_version(row: dict | None) -> str:
    """Marker that changes whenever a field the answer can depend on changes."""
    if not row:
        return NO_RECORD
    return hashlib.sha256(listing_context(row).encode()).hexdigest()[:16]


class SemanticCache:
    def __init__(self, threshold: float = 0.85, check_version: bool = True, host: str | None = None):
        from sentence_transformers import SentenceTransformer

        self.threshold = threshold
        self.check_version = check_version
        self.redis_client = redis.Redis(host=host or os.getenv("REDIS_HOST", "localhost"), port=6379)
        self.model = SentenceTransformer(MODEL_NAME, device="cpu")
        self.ensure_index()

    def ensure_index(self) -> None:
        try:
            self.redis_client.ft(INDEX).info()
        except redis.ResponseError:
            fields = [TextField("query"), TagField("listing_id"),
                      VectorField("embedding", "FLAT", {"TYPE": "FLOAT32", "DIM": EMBED_DIM,
                                                        "DISTANCE_METRIC": "COSINE"})]
            self.redis_client.ft(INDEX).create_index(
                fields, definition=IndexDefinition(prefix=[ENTRY_PREFIX], index_type=IndexType.HASH))

    def embed(self, text_value: str) -> bytes:
        return np.asarray(self.model.encode(text_value, normalize_embeddings=True), dtype=np.float32).tobytes()

    def nearest(self, embedding: bytes) -> dict | None:
        """Closest stored query, with cosine similarity (1 - Redis cosine distance)."""
        query = (Query("*=>[KNN 1 @embedding $vec AS distance]").sort_by("distance").dialect(2)
                 .return_fields("query", "answer", "data_version", "listing_id", "answer_key", "distance"))
        docs = self.redis_client.ft(INDEX).search(query, query_params={"vec": embedding}).docs
        if not docs:
            return None
        doc = docs[0]
        return {"key": doc.id, "query": doc.query, "answer": doc.answer, "data_version": doc.data_version,
                "listing_id": doc.listing_id, "answer_key": getattr(doc, "answer_key", ""),
                "similarity": 1 - float(doc.distance)}

    def lookup(self, question: str) -> dict:
        """Returns the nearest entry when it can be served, or why it cannot."""
        embedding = self.embed(question)
        entry = self.nearest(embedding)
        similarity = entry["similarity"] if entry else 0.0
        if not entry or similarity < self.threshold:
            return {"hit": False, "similarity": similarity, "embedding": embedding, "entry": entry, "stale": False}
        if self.check_version and self.is_stale(entry):
            self.redis_client.delete(entry["key"])
            logger.info("STALE entry dropped: similarity=%.4f query=%r", similarity, entry["query"])
            return {"hit": False, "similarity": similarity, "embedding": embedding, "entry": entry, "stale": True}
        return {"hit": True, "similarity": similarity, "embedding": embedding, "entry": entry, "stale": False}

    @staticmethod
    def is_stale(entry: dict) -> bool:
        if entry["data_version"] == NO_RECORD:
            return False
        with engine.connect() as conn:
            row = conn.execute(text("SELECT id, property_address, monthly_rent, property_category, available_units "
                                    "FROM listings WHERE id = :id"), {"id": int(entry["listing_id"])}).mappings().first()
        return data_version(dict(row) if row else None) != entry["data_version"]

    def store(self, question: str, embedding: bytes, answer: str, row: dict | None, answer_key: str = "") -> None:
        self.redis_client.hset(f"{ENTRY_PREFIX}{uuid.uuid4().hex}", mapping={
            "query": question, "embedding": embedding, "answer": answer, "data_version": data_version(row),
            "listing_id": str(row["id"]) if row else NO_RECORD, "answer_key": answer_key, "created_at": time.time()})

    def clear(self) -> None:
        keys = list(self.redis_client.scan_iter(f"{ENTRY_PREFIX}*", count=500))
        if keys:
            self.redis_client.delete(*keys)


def answer_question(cache: SemanticCache, question: str, agent, answer_key: str = "") -> dict:
    """Ingress: serve from the cache, or run the agent pipeline and store its final answer."""
    start = time.perf_counter()
    found = cache.lookup(question)
    search_ms = (time.perf_counter() - start) * 1000
    if found["hit"]:
        latency = (time.perf_counter() - start) * 1000
        logger.info("CACHE HIT similarity=%.4f latency_ms=%.1f query=%r", found["similarity"], latency, question)
        entry = found["entry"]
        return {"question": question, "answer": entry["answer"], "is_cached": True,
                "similarity": round(found["similarity"], 4), "latency_ms": round(latency, 1), "search_ms": round(search_ms, 1),
                "cached_query": entry["query"], "cached_key": entry["answer_key"], "status": "cached", "stale_dropped": False}

    logger.info("CACHE MISS best_similarity=%.4f query=%r", found["similarity"], question)
    row = find_listing(question)
    final = agent(question, listing_context(row))
    latency = (time.perf_counter() - start) * 1000
    answer = final.get("answer", "") if final else ""
    status = final.get("status", "timeout") if final else "timeout"
    if status == "approved" and answer:  # only approved answers are reused
        cache.store(question, found["embedding"], answer, row, answer_key)
    agent_ms = final.get("agent_ms") if final else None
    if agent_ms is not None:  # replayed agent answer: its recorded time stands in for the agent call
        latency = search_ms + agent_ms
    return {"question": question, "answer": answer, "is_cached": False, "similarity": round(found["similarity"], 4),
            "latency_ms": round(latency, 1), "search_ms": round(search_ms, 1), "cached_query": None, "cached_key": None,
            "status": status, "stale_dropped": found["stale"]}
