import json
from typing import Any

from .hw5_contracts import (
    FixtureStore,
    envelope,
    listing_detail,
    listing_summary,
    search_listings,
)

STORE = FixtureStore()


def execute_tool(
    name: str,
    inputs: dict[str, Any] | None,
    store: FixtureStore | None = None,
) -> str:
    """
    Safe entry point for all three domain tools.
    Always returns a JSON string and never crashes the caller.
    """

    store = store or STORE
    inputs = inputs if isinstance(inputs, dict) else {}

    try:
        # HW5 safety rule
        if (
            name == "listing_summary"
            and inputs.get("include_private") is True
        ):
            result = envelope(
                False,
                error=(
                    "blocked by safety rule: "
                    "private owner data is not returned"
                ),
            )

        elif name == "search_listings":
            result = search_listings(
                store,
                inputs.get("query"),
                inputs.get("limit", 10),
            )

        elif name == "listing_detail":
            result = listing_detail(
                store,
                inputs.get("listing_id"),
            )

        elif name == "listing_summary":
            result = listing_summary(
                store,
                inputs.get("category"),
            )

        else:
            result = envelope(
                False,
                error=f"unknown tool: {name}",
            )

    except Exception as error:
        result = envelope(
            False,
            error=f"tool error: {type(error).__name__}: {error}",
        )

    return json.dumps(result, sort_keys=True)