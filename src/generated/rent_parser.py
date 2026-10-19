"""Rent-string parsing for listings (generated with AGENT.md, then corrected; see reports/hw06)."""
import re

_AMOUNT = re.compile(r"(-?)\s*\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", re.IGNORECASE)


def parse_monthly_rent(text: str) -> int:
    """Convert a listing's rent string into whole US dollars per month.

    Accepts forms such as "$2,400/mo", "2400 per month", "$2.4k" and " $1,950 ".

    Raises:
        ValueError: if the text is empty, contains no amount, or the amount is zero or negative.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("rent text is empty")
    match = _AMOUNT.search(text)
    if match is None:
        raise ValueError(f"no rent amount found in {text!r}")
    sign, number, thousands = match.groups()
    amount = float(number.replace(",", ""))
    if thousands:
        amount *= 1000
    if sign:
        amount = -amount
    rent = round(amount)
    if rent <= 0:
        raise ValueError(f"rent must be positive, got {rent}")
    return rent
