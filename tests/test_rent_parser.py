import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.generated.rent_parser import parse_monthly_rent  # noqa: E402


@pytest.mark.parametrize("text, expected", [
    ("$2,400/mo", 2400),
    ("2400 per month", 2400),
    ("$2.4k", 2400),
    ("  $1,950 ", 1950),
])
def test_parse_monthly_rent_valid(text, expected):
    assert parse_monthly_rent(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "call for price", "-$2,400", "$0"])
def test_parse_monthly_rent_rejects_invalid(text):
    with pytest.raises(ValueError):
        parse_monthly_rent(text)
