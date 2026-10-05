import json
import sys
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("s6758-meals")

BASE_URL = "https://www.themealdb.com/api/json/v1/1"


def call_api(endpoint, params=None):
    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool()
def search_meals_by_name(name: str, limit: int = 5) -> str:
    if not name.strip():
        return json.dumps({"ok": False, "error": "name is required"})

    data = call_api("search.php", {"s": name})
    meals = data.get("meals") or []

    return json.dumps({
        "ok": True,
        "data": meals[:limit],
    })


@mcp.tool()
def meals_by_ingredient(ingredient: str, limit: int = 5) -> str:
    if not ingredient.strip():
        return json.dumps({"ok": False, "error": "ingredient is required"})

    data = call_api("filter.php", {"i": ingredient})
    meals = data.get("meals") or []

    return json.dumps({
        "ok": True,
        "data": meals[:limit],
    })


@mcp.tool()
def random_meal() -> str:
    data = call_api("random.php")
    meals = data.get("meals") or []

    return json.dumps({
        "ok": True,
        "data": meals[0] if meals else None,
    })


@mcp.tool()
def meal_details(meal_id: str) -> str:
    data = call_api("lookup.php", {"i": meal_id})
    meals = data.get("meals") or []

    return json.dumps({
        "ok": True,
        "data": meals[0] if meals else None,
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")