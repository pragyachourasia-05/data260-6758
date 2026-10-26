"""HW7 Part 4: MRKL tools for the bike-share membership agent (pure functions + JSON schemas).

Every tool returns the common envelope
    {"success": bool, "data"?: any, "error"?: str, "source"?: str, "ts"?: str}

csv_sql           read-only SELECT over the uploaded trips (SQLite in memory, table `trips`)
policy_retriever  fetch the pricing page, extract text, return short quotable passages
calculator        safe arithmetic over a whitelisted expression (AST walk, no eval)
"""
from __future__ import annotations

import ast
import hashlib
import html
import math
import operator
import re
import sqlite3
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- common envelope


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def envelope(success: bool, data: Any = None, error: str | None = None, source: str | None = None) -> dict:
    out: dict[str, Any] = {"success": success, "ts": now_iso()}
    if success:
        out["data"] = data
    else:
        out["error"] = error
    if source:
        out["source"] = source
    return out


# ---------------------------------------------------------------- JSON schemas

TOOL_SCHEMAS = {
    "csv_sql": {
        "name": "csv_sql",
        "description": "Run ONE read-only SQLite SELECT over the uploaded trips table `trips` "
                       "(columns: ride_id, rideable_type, started_at, ended_at, start_station_name, "
                       "end_station_name, duration_min, billed_min = minutes rounded up for per-minute pricing, "
                       "month 'YYYY-MM', week 'YYYY-Www').",
        "input": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"],
                  "additionalProperties": False},
        "output": {"type": "object", "properties": {
            "rows": {"type": "array", "items": {"type": "object"}},
            "row_count": {"type": "number"}, "source": {"const": "uploaded.csv"}}},
    },
    "policy_retriever": {
        "name": "policy_retriever",
        "description": "Fetch the pricing page URL, extract its text and return the k passages that best "
                       "match the query (membership price, included minutes, per-minute rates, unlock fees).",
        "input": {"type": "object", "properties": {
            "url": {"type": "string"}, "query": {"type": "string"},
            "k": {"type": "integer", "minimum": 1, "maximum": 10}},
            "required": ["url", "query"], "additionalProperties": False},
        "output": {"type": "object", "properties": {"passages": {"type": "array", "items": {
            "type": "object", "properties": {"text": {"type": "string"}, "source": {"type": "string"},
                                             "score": {"type": "number"}}}}}},
    },
    "calculator": {
        "name": "calculator",
        "description": "Safe arithmetic: digits, + - * / ( ) . and spaces only.",
        "input": {"type": "object", "properties": {
            "expression": {"type": "string", "pattern": r"^[0-9+\-*/().\s]+$"}, "units": {"type": "string"}},
            "required": ["expression"], "additionalProperties": False},
        "output": {"type": "object", "properties": {"value": {"type": "number"}, "units": {"type": "string"}}},
    },
}

# ---------------------------------------------------------------- csv_sql

MAX_ROWS = 200
READ_ONLY_ENFORCED = True  # Part 5 baseline runs flip this to show the attack without the tool defense
_DB: dict[str, sqlite3.Connection] = {}


def load_trips(csv_path: str | Path) -> sqlite3.Connection:
    """Load the uploaded CSV into an in-memory SQLite table `trips` with helper columns."""
    import csv

    key = str(Path(csv_path).resolve())
    if key in _DB:
        return _DB[key]
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute(
        "CREATE TABLE trips (ride_id TEXT, rideable_type TEXT, started_at TEXT, ended_at TEXT, "
        "start_station_name TEXT, end_station_name TEXT, duration_min REAL, billed_min INTEGER, month TEXT, week TEXT)"
    )
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            start = datetime.fromisoformat(r["started_at"])
            end = datetime.fromisoformat(r["ended_at"])
            iso = start.isocalendar()
            rows.append((r.get("ride_id"), r.get("rideable_type"), r["started_at"], r["ended_at"],
                         r.get("start_station_name"), r.get("end_station_name"),
                         round((end - start).total_seconds() / 60, 3),
                         math.ceil((end - start).total_seconds() / 60 - 1e-9), start.strftime("%Y-%m"),
                         f"{iso[0]}-W{iso[1]:02d}"))
    conn.executemany("INSERT INTO trips VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    _DB[key] = conn
    return conn


def _read_only_authorizer(action, arg1, arg2, dbname, source):
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
    return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY


def check_select_contract(sql: str) -> str | None:
    """Tool-boundary rule: exactly one statement, and it must be a SELECT (or WITH ... SELECT)."""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        return "sql is empty"
    if ";" in stripped:
        return "only one SQL statement is allowed"
    if not re.match(r"(?is)^(select|with)\b", stripped):
        return "only read-only SELECT queries are allowed"
    return None


def csv_sql(sql: str, csv_path: str | Path) -> dict:
    if not isinstance(sql, str):
        return envelope(False, error="sql must be a string", source="uploaded.csv")
    conn = load_trips(csv_path)
    try:
        if READ_ONLY_ENFORCED:
            problem = check_select_contract(sql)
            if problem:
                return envelope(False, error=f"rejected: {problem}", source="uploaded.csv")
            conn.set_authorizer(_read_only_authorizer)  # second wall: SQLite refuses any write
            cur = conn.execute(sql)
        else:
            conn.set_authorizer(None)
            cur = conn.executescript(sql) if ";" in sql.strip().rstrip(";") else conn.execute(sql)
        cols = [d[0] for d in (cur.description or [])]
        data = [dict(zip(cols, row, strict=False)) for row in cur.fetchmany(MAX_ROWS)] if cols else []
        return envelope(True, {"rows": data, "row_count": len(data), "source": "uploaded.csv"}, source="uploaded.csv")
    except sqlite3.Error as exc:
        return envelope(False, error=f"sql error: {exc}", source="uploaded.csv")
    finally:
        conn.set_authorizer(None)


# ---------------------------------------------------------------- policy_retriever

_PAGES: dict[str, dict] = {}
_FETCH_LOCK = threading.Lock()  # one fetch per URL even when tool calls run in parallel


def fetch_page(url: str) -> dict:
    """Fetch once per process; local paths (the Part 5 fixture) are read from disk."""
    with _FETCH_LOCK:
        if url in _PAGES:
            return _PAGES[url]
        return _fetch_uncached(url)


def _fetch_uncached(url: str) -> dict:
    if re.match(r"^https?://", url):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (DATA-260 coursework)"})
        raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", errors="ignore")
    else:
        raw = Path(url.removeprefix("file://")).read_text(encoding="utf-8")
    passages = extract_passages(raw, url)
    text = "\n".join(p for p in passages)
    page = {"url": url, "captured_at": now_iso(), "passages": passages, "text": text,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "raw_html_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest()}
    _PAGES[url] = page
    return page


def _clean(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def extract_passages(raw: str, url: str) -> list[str]:
    """Short quotable passages: comparison-table cells labelled with their plan, then page text."""
    passages: list[str] = []
    headers = [_clean(h) for h in re.findall(r"<h\d[^>]*>(.*?)</h\d>", raw, re.S)]
    if "Compare your options" in headers:
        start = headers.index("Compare your options") + 1
        plans = [h for h in headers[start:start + 8] if h][:5]
    else:
        plans = []
    flat = _clean(re.sub(r"(?is)<(script|style|svg)\b.*?</\1>", " ", raw))
    if plans:  # plan prices appear right after the plan names, e.g. "$29/month"
        after = flat[flat.find(plans[-1]) + len(plans[-1]):]
        prices = re.findall(r"\$\d[\d.,]*(?:/\w+)?", after)[: len(plans)]
        if len(prices) == len(plans):
            passages.append("Plan prices: " + "; ".join(f"{p} {v}" for p, v in zip(plans, prices, strict=True)) + ".")
    cells = re.findall(r'<div[^>]*\bcol="\d+"[^>]*\bidx="(\d+)"[^>]*>(.*?)</p>', raw, re.S)
    row: list[str] = []
    seen = set()
    for idx, cell in cells + [("0", "")]:
        if idx == "0" and row:
            label, values = row[0], row[1:]
            for plan, value in zip(plans, values, strict=False):
                text = f"{plan} - {label}: {value}."
                if value and text not in seen:
                    seen.add(text)
                    passages.append(text)
            row = []
        row.append(_clean(cell))
    # remaining visible text in ~30-word windows (FAQs, fine print)
    words = flat.split()
    for i in range(0, len(words), 30):
        chunk = " ".join(words[i:i + 30])
        if "$" in chunk or re.search(r"\b(min|minute|unlock|pass|member|fee|overage|charge)", chunk, re.I):
            passages.append(chunk)
    return passages


def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9$.]+", s.lower())


def policy_retriever(url: str, query: str, k: int = 4) -> dict:
    if not isinstance(url, str) or not url.strip():
        return envelope(False, error="url must be a non-empty string")
    if not isinstance(query, str) or not query.strip():
        return envelope(False, error="query must be a non-empty string")
    k = max(1, min(int(k or 4), 10))
    try:
        page = fetch_page(url.strip())
    except Exception as exc:  # network or file problems become a tool error, not a crash
        return envelope(False, error=f"fetch failed: {type(exc).__name__}: {exc}", source=url)
    q = set(_tokens(query))
    scored = []
    for text in page["passages"]:
        t = _tokens(text)
        overlap = sum(1 for w in set(t) if w in q)
        score = overlap / (1 + len(q)) + (0.15 if "$" in text else 0) + (0.1 if len(text) < 140 else 0)
        scored.append((round(score, 3), text))
    scored.sort(key=lambda s: s[0], reverse=True)
    passages = [{"text": text, "source": url, "score": score} for score, text in scored[:k] if score > 0]
    return envelope(True, {"passages": passages, "captured_at": page["captured_at"], "sha256": page["sha256"]},
                    source=url)


# ---------------------------------------------------------------- calculator

_CALC_RE = re.compile(r"^[0-9+\-*/().\s]+$")
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval_node(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    raise ValueError(f"unsupported syntax: {type(node).__name__}")


def calculator(expression: str, units: str | None = None) -> dict:
    if not isinstance(expression, str) or not _CALC_RE.match(expression) or len(expression) > 200:
        return envelope(False, error="expression may only contain digits, + - * / ( ) . and spaces")
    try:
        value = _eval_node(ast.parse(expression, mode="eval").body)
    except ZeroDivisionError:
        return envelope(False, error="division by zero")
    except (SyntaxError, ValueError) as exc:
        return envelope(False, error=f"invalid expression: {exc}")
    data = {"value": round(value, 4)}
    if units:
        data["units"] = units
    return envelope(True, data)
