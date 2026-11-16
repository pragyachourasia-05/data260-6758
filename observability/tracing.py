"""HW10 Part 4: structured JSON spans. The HW8 correlation_id is the trace_id everywhere.

Every stage appends one line to reports/hw10/raw/spans.jsonl (override with HW10_SPANS):
    {"trace_id", "stage", "start", "end", "start_ts", "end_ts", "duration_ms", "status", "error", ...extra}
"""
from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPANS = Path(os.getenv("HW10_SPANS", ROOT / "reports" / "hw10" / "raw" / "spans.jsonl"))
_lock = threading.Lock()


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_span(trace_id: str | None, stage: str, start_ts: float, end_ts: float, status: str = "ok",
               error: str | None = None, **extra) -> dict:
    span = {"trace_id": trace_id, "stage": stage, "start": iso(start_ts), "end": iso(end_ts),
            "start_ts": round(start_ts, 6), "end_ts": round(end_ts, 6),
            "duration_ms": round((end_ts - start_ts) * 1000, 1), "status": status, "error": error, **extra}
    SPANS.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(span) + "\n").encode("utf-8")
    with _lock, SPANS.open("ab") as f:
        _file_lock(f)  # several processes append to this file; on Windows "a" alone is not atomic across them
        try:
            f.seek(0, os.SEEK_END)
            f.write(line)
            f.flush()
        finally:
            _file_unlock(f)
    return span


def _file_lock(f) -> None:
    if os.name == "nt":
        import msvcrt

        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)  # retries for about 10 s, then raises
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_EX)


def _file_unlock(f) -> None:
    if os.name == "nt":
        import msvcrt

        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


@contextmanager
def span(trace_id: str | None, stage: str, **extra):
    """Times a block. Fields added to the yielded dict go into the span; an exception marks it as an error."""
    fields = dict(extra)
    start = time.time()
    try:
        yield fields
    except Exception as exc:
        write_span(trace_id, stage, start, time.time(), "error", f"{type(exc).__name__}: {exc}", **fields)
        raise
    write_span(trace_id, stage, start, time.time(), fields.pop("status", "ok"), fields.pop("error", None), **fields)


def queue_span(trace_id: str | None, topic: str, sent_ts: float | None, received_ts: float) -> None:
    """Time a message waited in a Kafka topic, from the producer's send to the consumer's receive."""
    if sent_ts:
        write_span(trace_id, f"queue:{topic}", sent_ts, received_ts, topic=topic)


def load_spans(path: Path = SPANS) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
