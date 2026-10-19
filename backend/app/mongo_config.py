"""HW6 server configuration for the MongoDB document API and chat memory.

Every value can be overridden with an environment variable (or backend/.env).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")

SID4 = 6758
PORT_BASE = 8000 + (SID4 % 900)  # 8458
PREFIX = f"s{SID4}"
SEED = SID4
VERIFY_SEED = 260000 + SID4

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", f"{PREFIX}_doc")

# Part 2 memory settings
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
NUM_CTX = int(os.getenv("NUM_CTX", "8192"))
SHORT_TERM_N = int(os.getenv("SHORT_TERM_N", "12"))
SUMMARIZE_EVERY_USER_MSGS = int(os.getenv("SUMMARIZE_EVERY_USER_MSGS", "4"))
LIFETIME_EVERY_SESSION_SUMMARIES = int(os.getenv("LIFETIME_EVERY_SESSION_SUMMARIES", "2"))
EPISODIC_TOP_K = int(os.getenv("EPISODIC_TOP_K", "3"))
MAX_FACTS_PER_MESSAGE = 3

# "hash" = local feature-hashing embedding (no extra model needed);
# "ollama" = Ollama /api/embed with EMBED_MODEL (e.g. nomic-embed-text).
EMBED_BACKEND = os.getenv("EMBED_BACKEND", "hash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
EMBED_DIM = int(os.getenv("EMBED_DIM", "512"))

# Part 3 usage log (one JSON line per /api/chat request)
USAGE_LOG = Path(os.getenv("USAGE_LOG", str(ROOT_DIR / "reports" / "hw06" / "raw" / "chat_usage.jsonl")))
