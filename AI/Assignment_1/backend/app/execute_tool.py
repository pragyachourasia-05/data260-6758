import json
from typing import Any

try:
    from .hw5_contracts import (
        FixtureStore,
        envelope,
        listing_detail,
        listing_summary,
        search_listings,
    )
except ImportError:
    from hw5_contracts import (
        FixtureStore,
        envelope,
        listing_detail,
        listing_summary,
        search_listings,
    )


STORE = FixtureStore()


def execute_tool(
    name: str,
    inputs: dict[str, Any] | None = None,
    store: FixtureStore | None = None,
) -> str:
    """
    Safe entry point for all domain tools.
    Always returns a JSON string.
    """

    active_store = store or STORE
    arguments = inputs if isinstance(inputs, dict) else {}

    try:
        # Safety rule: private owner information cannot be returned.
        if (
            name == "listing_summary"
            and arguments.get("include_private") is True
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
                active_store,
                arguments.get("query"),
                arguments.get("limit", 10),
            )

        elif name == "listing_detail":
            result = listing_detail(
                active_store,
                arguments.get("listing_id"),
            )

        elif name == "listing_summary":
            result = listing_summary(
                active_store,
                arguments.get("category"),
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