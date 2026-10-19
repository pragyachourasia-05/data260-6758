# test_rent_parser.py
import pytest
from src.generated.rent_parser import parse_monthly_rent

def test_parse_monthly_rent_valid():
    assert parse_monthly_rent("$2,400/mo") == 2400
    assert parse_monthly_rent("2400 per month") == 2400
    assert parse_monthly_rent("$2.4k") == 2400
    assert parse_monthly_rent("  $1,950 ") == 1950

def test_parse_monthly_rent_empty():
    with pytest.raises(ValueError):
        parse_monthly_rent("")

def test_parse_monthly_rent_no_number():
    with pytest.raises(ValueError):
        parse_monthly_rent("$2,400")

def test_parse_monthly_rent_negative():
    with pytest.raises(ValueError):
        parse_monthly_rent("-$2,400")

def test_parse_monthly_rent_zero():
    with pytest.raises(ValueError):
        parse_monthly_rent("$0")
