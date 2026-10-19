"""Offline tests for src/file_memory.py (no model, network or database)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.file_memory import (  # noqa: E402
    build_system_prompt,
    compact,
    consolidate_memory,
    count_memory_lines,
    needs_consolidation,
    read_last_consolidated,
)

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
ORIGINAL = (ROOT / "reports" / "hw06" / "memory" / "MEMORY_original.md").read_text(encoding="utf-8")


class FakeClient:
    def complete(self, messages):
        return {"text": "- earlier turns summarized", "input_tokens": 0, "output_tokens": 0}


def test_comment_and_blank_lines_are_not_counted():
    text = "<!-- last_consolidated: 2026-10-18T00:00:00+00:00 -->\n# MEMORY\n\n- [2026-10-01] a: b\n"
    assert count_memory_lines(text) == 2


def test_original_test_file_is_55_lines_and_needs_consolidation():
    assert len(ORIGINAL.splitlines()) == 55
    due, reasons = needs_consolidation(ORIGINAL, NOW)
    assert due and len(reasons) == 2


def test_fresh_small_file_does_not_need_consolidation():
    text = f"<!-- last_consolidated: {(NOW - timedelta(hours=1)).isoformat()} -->\n# MEMORY\n- [2026-10-18] a: b\n"
    assert needs_consolidation(text, NOW) == (False, [])


def test_old_timestamp_alone_triggers_consolidation():
    text = "<!-- last_consolidated: 2026-10-01T00:00:00Z -->\n# MEMORY\n- [2026-10-01] a: b\n"
    due, reasons = needs_consolidation(text, NOW)
    assert due and "24 h" in reasons[0]


def test_missing_or_bad_timestamp_reads_as_none():
    assert read_last_consolidated("# MEMORY") is None
    assert read_last_consolidated("<!-- last_consolidated: yesterday -->") is None


def test_consolidation_shrinks_below_40_lines_and_merges_duplicates():
    text, report = consolidate_memory(ORIGINAL, NOW)
    assert len(text.splitlines()) < 40
    assert report.facts_after < report.facts_before
    assert len(report.duplicates_merged) >= 3
    assert "ollama_url: http://localhost:11434 (seen 3x)" in text


def test_contradictions_are_recorded_not_silently_deleted():
    text, report = consolidate_memory(ORIGINAL, NOW)
    assert len(report.contradictions) >= 3
    for c in report.contradictions:
        assert c["dropped"] in text  # the losing value is still visible
    assert "budget: $2,700 per month" in text


def test_hedged_newer_value_does_not_win():
    text, _ = consolidate_memory(ORIGINAL, NOW)
    assert "cat_name: Miso" in text
    assert 'kept "Miso"' in text


def test_suspicious_resolution_is_flagged_for_review():
    _, report = consolidate_memory(ORIGINAL, NOW)
    assert [r["key"] for r in report.needs_review] == ["mongo_db"]


def test_consolidation_is_idempotent_and_keeps_history():
    once, _ = consolidate_memory(ORIGINAL, NOW)
    twice, report = consolidate_memory(once, NOW)
    assert once == twice
    assert report.contradictions == []


def test_system_prompt_contains_agent_rules_and_facts_but_not_comments():
    prompt = build_system_prompt("# Agent Instructions\n- rule", ORIGINAL)
    assert prompt.startswith("# Agent Instructions")
    assert "cat_name: Miso" in prompt
    assert "last_consolidated" not in prompt


def test_compact_reports_before_and_after_counts(tmp_path):
    mem = tmp_path / "MEMORY.md"
    mem.write_text(ORIGINAL, encoding="utf-8")
    convo = [{"role": "system", "content": "s"}] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)
    ]
    result = compact(convo, FakeClient(), memory_path=mem)
    assert (result["messages_before"], result["messages_after"]) == (11, 6)
    assert result["memory_lines_before"] == 50 and result["memory_lines_after"] < 40
    assert count_memory_lines(mem.read_text(encoding="utf-8")) == result["memory_lines_after"]


def test_compact_rejects_negative_keep_last(tmp_path):
    with pytest.raises(ValueError):
        compact([{"role": "system", "content": "s"}], FakeClient(), memory_path=tmp_path / "MEMORY.md", keep_last=-1)


def test_user_correction_clears_review_flag():
    once, _ = consolidate_memory(ORIGINAL, NOW)
    corrected = once.replace("## Environment", "- [2026-10-19] mongo_db: s6758_doc\n## Environment", 1)
    text, report = consolidate_memory(corrected, NOW)
    assert "mongo_db: s6758_doc" in text
    assert "## Needs review" not in text
    assert report.contradictions[0]["dropped"] == "study_planner_demo"
