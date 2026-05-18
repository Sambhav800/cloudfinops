import pytest
from app.bill_parser.pdf_parser import parse_pdf_invoice

# Synthetic AWS-format PDF content (text-based, no real PDF needed)
# Test _normalize_amount_token directly
from app.bill_parser.pdf_parser import _normalize_amount_token


def test_bare_decimal_parsed_as_usd():
    amount, currency = _normalize_amount_token("1,234.56")
    assert amount == 1234.56
    assert currency == "USD"


def test_bare_decimal_small():
    amount, currency = _normalize_amount_token("45.23")
    assert amount == 45.23
    assert currency == "USD"


def test_with_dollar_sign():
    amount, currency = _normalize_amount_token("$1,234.56")
    assert amount == 1234.56


def test_parenthesized_credit_not_parsed():
    amount, currency = _normalize_amount_token("(USD 8.33)")
    assert amount is None
    assert currency is None


def test_pure_integer_not_parsed():
    # "730" (a quantity) should NOT be parsed as an amount
    # because it has no decimal places
    amount, _ = _normalize_amount_token("730")
    assert amount is None


def test_unit_string_not_parsed():
    amount, _ = _normalize_amount_token("Hrs")
    assert amount is None
