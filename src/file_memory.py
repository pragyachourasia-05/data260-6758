"""HW6 Part 4: file-based memory with AGENT.md (instructions) and MEMORY.md (facts).

MEMORY.md format
    <!-- last_consolidated: 2026-10-18T09:00:00+00:00 -->
    # MEMORY
    ## <Section>
    - [YYYY-MM-DD] key: value

Consolidation (consolidate_memory) is deterministic, so the same file always gives
the same result and every decision is written back into the file:
  * duplicates   - same key and same normalized value -> one line, "(seen Nx)"
  * conflicts    - same key, different values -> the newest dated value wins,
                   unless it is hedged ("?", "maybe", "might", "not sure"), in
                   which case the newest confident value wins
  * nothing is dropped silently: every losing value is listed under
    "## Resolved contradictions" with the rule that decided it
  * a reviewer pass flags resolutions that look wrong (the losing value was
    stated more often than the winner) under "## Needs review"
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "AGENT.md"
MEMORY_PATH = ROOT / "MEMORY.md"

MAX_MEMORY_LINES = 40
MAX_AGE = timedelta(hours=24)

_STAMP_RE = re.compile(r"<!--\s*last_consolidated:\s*(\S+)\s*-->")
_FACT_RE = re.compile(r"^-\s*\[(\d{4}-\d{2}-\d{2})\]\s*([^:]+):\s*(.+?)\s*$")
_SEEN_RE = re.compile(r"\s*\(seen (\d+)x\)\s*$")
_HEDGES = ("?", "maybe", "might", "not sure", "probably", "i think")


class ChatClient(Protocol):
    """Anything with ModelClient.complete(messages) -> {"text": ...}."""

    def complete(self, messages: list[dict]) -> dict:
        """Send chat messages to the model and return its reply and token counts."""
        ...


# ---------------------------------------------------------------------------
# Loading + prompt construction
# ---------------------------------------------------------------------------
def load_memory_files(agent_path: Path = AGENT_PATH, memory_path: Path = MEMORY_PATH) -> tuple[str, str]:
    """Return (AGENT.md text, MEMORY.md text); a missing file reads as empty."""
    agent = agent_path.read_text(encoding="utf-8") if agent_path.exists() else ""
    memory = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
    return agent, memory


def build_system_prompt(agent_text: str, memory_text: str) -> str:
    """AGENT.md instructions first, then the durable facts from MEMORY.md."""
    facts = "\n".join(line for line in memory_text.splitlines() if is_content_line(line))
    return (
        f"{agent_text.strip()}\n\n"
        "# Long-term memory (from MEMORY.md)\n"
        "Facts learned in earlier conversations. Treat them as true unless the user corrects them.\n"
        f"{facts or '(no saved facts yet)'}"
    )


# ---------------------------------------------------------------------------
# Consolidation checks
# ---------------------------------------------------------------------------
def is_content_line(line: str) -> bool:
    """Non-empty and not an HTML comment line."""
    s = line.strip()
    return bool(s) and not (s.startswith("<!--") and s.endswith("-->"))


def count_memory_lines(memory_text: str) -> int:
    """Number of non-empty, non-comment lines (the 40-line consolidation threshold)."""
    return sum(1 for line in memory_text.splitlines() if is_content_line(line))


def read_last_consolidated(memory_text: str) -> datetime | None:
    """Parse the <!-- last_consolidated: ISO --> marker; None if missing or malformed."""
    match = _STAMP_RE.search(memory_text)
    if not match:
        return None
    try:
        stamp = datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def needs_consolidation(memory_text: str, now: datetime | None = None) -> tuple[bool, list[str]]:
    """Consolidate when > 40 content lines or the last consolidation is > 24 h old (or missing)."""
    now = now or datetime.now(timezone.utc)
    reasons = []
    n = count_memory_lines(memory_text)
    if n > MAX_MEMORY_LINES:
        reasons.append(f"{n} non-empty, non-comment lines > {MAX_MEMORY_LINES}")
    stamp = read_last_consolidated(memory_text)
    if stamp is None:
        reasons.append("no last_consolidated timestamp")
    elif now - stamp > MAX_AGE:
        reasons.append(f"last consolidated {(now - stamp).total_seconds() / 3600:.1f} h ago (> 24 h)")
    return bool(reasons), reasons


# ---------------------------------------------------------------------------
# Consolidation
# ---------------------------------------------------------------------------
@dataclass
class Fact:
    day: str
    key: str
    value: str
    section: str
    line_no: int
    seen: int = 1  # merged duplicates carry their count as "(seen Nx)"

    @property
    def norm_key(self) -> str:
        """Key in snake_case, so "Cat name" and "cat_name" match."""
        return re.sub(r"[^a-z0-9]+", "_", self.key.lower()).strip("_")

    @property
    def norm_value(self) -> str:
        """Value with case and punctuation removed, for duplicate detection."""
        return re.sub(r"[^a-z0-9$?]+", " ", self.value.lower()).strip()

    @property
    def hedged(self) -> bool:
        """True if the value is uncertain ("Mochi?", "maybe ...")."""
        v = self.value.lower()
        return any(h in v for h in _HEDGES)


@dataclass
class ConsolidationReport:
    lines_before: int
    lines_after: int = 0
    facts_before: int = 0
    facts_after: int = 0
    duplicates_merged: list[str] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    needs_review: list[dict] = field(default_factory=list)


def parse_facts(memory_text: str) -> tuple[list[Fact], list[str]]:
    """Return (facts, other content lines that are not facts or headings)."""
    facts, other, section = [], [], "General"
    for i, line in enumerate(memory_text.splitlines(), 1):
        s = line.strip()
        if not is_content_line(s) or s.startswith("# "):
            continue
        if s.startswith("## "):
            section = s[3:].strip()
            continue
        m = _FACT_RE.match(s)
        if m and section not in ("Resolved contradictions", "Needs review"):
            seen = _SEEN_RE.search(m.group(3))
            facts.append(Fact(m.group(1), m.group(2).strip(), _SEEN_RE.sub("", m.group(3)), section, i,
                              int(seen.group(1)) if seen else 1))
        elif section not in ("Resolved contradictions", "Needs review"):
            other.append(s)
    return facts, other


def consolidate_memory(memory_text: str, now: datetime | None = None) -> tuple[str, ConsolidationReport]:
    """Merge duplicates, resolve contradictions explicitly and flag doubtful resolutions.

    Returns the new MEMORY.md text and a report of every decision (see module docstring).
    """
    now = now or datetime.now(timezone.utc)
    report = ConsolidationReport(lines_before=count_memory_lines(memory_text))
    facts, other = parse_facts(memory_text)
    report.facts_before = len(facts)

    # Keep earlier resolution history and review flags so repeated consolidation does not forget them.
    history, old_review = [], []
    current = None
    for line in memory_text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            current = s[3:].strip()
            continue
        if current == "Resolved contradictions" and s.startswith("- "):
            history.append(s)
        elif current == "Needs review" and s.startswith("- "):
            old_review.append(s)

    by_key: dict[str, list[Fact]] = {}
    for f in facts:
        by_key.setdefault(f.norm_key, []).append(f)

    kept: list[tuple[Fact, int, int]] = []  # (winning fact, times seen, first line of the key)
    new_history: list[str] = []
    for key, group in by_key.items():
        variants: dict[str, list[Fact]] = {}
        for f in group:
            variants.setdefault(f.norm_value, []).append(f)
        weight = {v: sum(f.seen for f in fs) for v, fs in variants.items()}
        for dupes in variants.values():
            if len(dupes) > 1:
                report.duplicates_merged.append(f"{dupes[0].key}: {dupes[0].value} (x{len(dupes)})")
        first_line = min(f.line_no for f in group)
        if len(variants) == 1:
            only = next(iter(variants.values()))
            kept.append((max(only, key=lambda f: f.day), weight[only[0].norm_value], first_line))
            continue

        latest = {v: max(fs, key=lambda f: (f.day, f.line_no)) for v, fs in variants.items()}
        ordered = sorted(latest.values(), key=lambda f: (f.day, f.line_no), reverse=True)
        confident = [f for f in ordered if not f.hedged]
        winner = confident[0] if confident else ordered[0]
        rule = "newest value" if winner is ordered[0] else "newer value is hedged/uncertain, kept newest confident value"
        kept.append((winner, weight[winner.norm_value], first_line))
        for loser in ordered:
            if loser is winner:
                continue
            count_l, count_w = weight[loser.norm_value], weight[winner.norm_value]
            entry = {"key": winner.norm_key, "kept": winner.value, "kept_date": winner.day, "kept_count": count_w,
                     "dropped": loser.value, "dropped_date": loser.day, "dropped_count": count_l, "rule": rule}
            report.contradictions.append(entry)
            new_history.append(f'- {winner.norm_key}: kept "{winner.value}" ({winner.day}) over '
                               f'"{loser.value}" ({loser.day}) - {rule}')
            if count_l > count_w:
                report.needs_review.append({**entry, "reason": f'it was stated {count_w}x while the dropped '
                                                               f'"{loser.value}" was stated {count_l}x'})

    sections: dict[str, list[str]] = {}
    for f, seen, _ in sorted(kept, key=lambda t: t[2]):
        suffix = f" (seen {seen}x)" if seen > 1 else ""
        sections.setdefault(f.section, []).append(f"- [{f.day}] {f.norm_key}: {f.value}{suffix}")

    out = [f"<!-- last_consolidated: {now.isoformat(timespec='seconds')} -->", "# MEMORY",
           "<!-- Durable facts. Format: - [YYYY-MM-DD] key: value. Consolidated by src/file_memory.py -->"]
    for name, lines in sections.items():
        out += [f"## {name}", *lines]
    if other:
        out += ["## Notes", *[f"- {o.lstrip('- ')}" for o in other]]
    resolved = history + [h for h in new_history if h not in history]
    if resolved:
        out += ["## Resolved contradictions", *resolved]
    # A flag is obsolete once its key has been decided again (e.g. the user corrected it).
    redecided = {c["key"] for c in report.contradictions}
    old_review = [r for r in old_review if r[2:].split(":", 1)[0].strip() not in redecided]
    review = old_review + [
        f'- {r["key"]}: kept "{r["kept"]}" by recency, but {r["reason"]} - likely resolved incorrectly, confirm with the user'
        for r in report.needs_review
    ]
    if review:
        out += ["## Needs review", *dict.fromkeys(review)]
    text = "\n".join(out) + "\n"
    report.lines_after = count_memory_lines(text)
    report.facts_after = sum(len(v) for v in sections.values())
    return text, report


# ---------------------------------------------------------------------------
# /dream: extract durable facts from the recent conversation
# ---------------------------------------------------------------------------
DREAM_PROMPT = (
    "From the conversation below, list durable facts about the user or the project that "
    "will still matter in future conversations (names, preferences, decisions, settings). "
    "Ignore small talk and one-off questions.\n"
    'Return JSON: {"facts": [{"section": "User" | "Project" | "Environment", '
    '"key": "<short_snake_case_key>", "value": "<short value>"}]} with at most 5 facts.\n\n'
)


def dream(conversation: list[dict], client: ChatClient, memory_path: Path = MEMORY_PATH, today: date | None = None) -> list[str]:
    """Ask the model for durable facts in recent turns and append the new ones to MEMORY.md."""
    today = today or date.today()
    recent = [m for m in conversation if m["role"] != "system"][-12:]
    if not recent:
        return []
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
    text = memory_path.read_text(encoding="utf-8") if memory_path.exists() else "# MEMORY\n"
    facts = parse_facts(text)[0]
    # Reusing existing keys is what lets consolidation treat a correction as a contradiction.
    known = "\n".join(f"- {f.norm_key} ({f.section}): {f.value}" for f in facts) or "(none)"
    prompt = (
        DREAM_PROMPT
        + "Facts already in MEMORY.md. If a new fact updates or corrects one of these, reuse its exact "
        + 'key and section, and keep the same units and formatting as the old value (e.g. "$2,700 per month"):\n'
        + f"{known}\n\nConversation:\n{transcript}"
    )
    result = client.complete([{"role": "user", "content": prompt}])
    try:
        items = json.loads(result["text"]).get("facts", [])
    except (json.JSONDecodeError, AttributeError):
        items = []

    existing = {(f.norm_key, f.norm_value) for f in facts}
    added = []
    for item in items[:5]:
        if not isinstance(item, dict) or not item.get("key") or not item.get("value"):
            continue
        fact = Fact(today.isoformat(), str(item["key"]).strip(), str(item["value"]).strip(),
                    str(item.get("section") or "User"), 0)
        if (fact.norm_key, fact.norm_value) in existing:
            continue
        existing.add((fact.norm_key, fact.norm_value))
        added.append((fact.section, f"- [{fact.day}] {fact.norm_key}: {fact.value}"))
    if added:
        text = _insert_into_sections(text, added)
        memory_path.write_text(text, encoding="utf-8")
    return [line for _, line in added]


def _insert_into_sections(text: str, additions: list[tuple[str, str]]) -> str:
    lines = text.rstrip("\n").splitlines()
    for section, new_line in additions:
        header = f"## {section}"
        if header in lines:
            idx = lines.index(header) + 1
            while idx < len(lines) and not lines[idx].startswith("## "):
                idx += 1
            lines.insert(idx, new_line)
        else:
            # New sections go before the bookkeeping sections.
            idx = next((i for i, l in enumerate(lines) if l in ("## Resolved contradictions", "## Needs review")), len(lines))
            lines[idx:idx] = [header, new_line]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# /compact: consolidate MEMORY.md and shrink the in-session conversation
# ---------------------------------------------------------------------------
def compact(conversation: list[dict], client: ChatClient, memory_path: Path = MEMORY_PATH, keep_last: int = 4) -> dict:
    """Consolidate MEMORY.md and replace older chat turns with one summary message.

    Returns before/after counts for both the conversation and MEMORY.md.
    """
    if keep_last < 0:
        raise ValueError(f"keep_last must be >= 0, got {keep_last}")
    msgs_before = len(conversation)
    system = [m for m in conversation if m["role"] == "system"][:1]
    turns = [m for m in conversation if m["role"] != "system"]
    if len(turns) > keep_last:
        old, recent = turns[:-keep_last], turns[-keep_last:]
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in old)
        summary = client.complete([{"role": "user", "content":
                                    "Summarize this conversation in at most 5 short bullet points:\n" + transcript}])["text"]
        conversation[:] = system + [{"role": "assistant", "content": f"Summary of earlier conversation:\n{summary.strip()}"}] + recent

    text = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
    new_text, report = consolidate_memory(text)
    memory_path.write_text(new_text, encoding="utf-8")
    return {
        "messages_before": msgs_before,
        "messages_after": len(conversation),
        "memory_lines_before": report.lines_before,
        "memory_lines_after": report.lines_after,
        "facts_before": report.facts_before,
        "facts_after": report.facts_after,
        "duplicates_merged": report.duplicates_merged,
        "contradictions": report.contradictions,
        "needs_review": report.needs_review,
    }
