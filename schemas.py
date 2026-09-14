from typing import List, Tuple
from pydantic import BaseModel, field_validator


class PlannerOutputSchema(BaseModel):
    """
    Strict schema Part 4 validates the Planner's raw output against, before
    it's allowed to reach the Reviewer. This is intentionally stricter than
    coerce_reply() in agents_demo.py, which silently repairs bad output --
    here we want real validation failures so the retry loop has something
    to actually do and measure.
    """
    tags: List[str]
    summary: str

    @field_validator("tags")
    @classmethod
    def exactly_three_tags_right_length(cls, v: List[str]) -> List[str]:
        if len(v) != 3:
            raise ValueError(f"expected exactly 3 tags, got {len(v)}")
        for i, tag in enumerate(v):
            if not (3 <= len(tag) <= 30):
                raise ValueError(f"tag[{i}]='{tag}' must be 3-30 characters, got {len(tag)}")
        return v

    @field_validator("summary")
    @classmethod
    def summary_at_most_25_words(cls, v: str) -> str:
        word_count = len(v.split())
        if word_count > 25:
            raise ValueError(f"summary must be at most 25 words, got {word_count}")
        return v


def validate_planner_data(data: dict) -> Tuple[bool, str]:
    """
    Returns (is_valid, error_message). error_message is empty on success,
    otherwise a human-readable string that gets fed back into the Planner's
    next retry prompt so it knows exactly what to fix.
    """
    try:
        PlannerOutputSchema(tags=data.get("tags", []), summary=data.get("summary", ""))
        return True, ""
    except Exception as e:
        return False, str(e)
