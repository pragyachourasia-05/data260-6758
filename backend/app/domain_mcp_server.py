import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Make the backend package importable when MCP Inspector loads this file directly.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.execute_tool import execute_tool


logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
)

mcp = FastMCP("s6758-rental-tools")


@mcp.tool()
def search_listings(query: str, limit: int = 10) -> str:
    return execute_tool(
        "search_listings",
        {
            "query": query,
            "limit": limit,
        },
    )


@mcp.tool()
def listing_detail(listing_id: int) -> str:
    return execute_tool(
        "listing_detail",
        {
            "listing_id": listing_id,
        },
    )


@mcp.tool()
def listing_summary(
    category: str | None = None,
    include_private: bool = False,
) -> str:
    return execute_tool(
        "listing_summary",
        {
            "category": category,
            "include_private": include_private,
        },
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")