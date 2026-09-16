import pytest
from app.bill_parser.pdf_parser import parse_pdf_invoice

# Synthetic AWS-format PDF content (text-based, no real PDF needed)
# Test _normalize_amount_token directly
from app.bill_parser.pdf_parser import _normalize_amount_token


def test_bare_decimal_preserves_unknown_currency():
    amount, currency = _normalize_amount_token("1,234.56")
    assert amount == 1234.56
    assert currency is None


def test_bare_decimal_small_preserves_unknown_currency():
    amount, currency = _normalize_amount_token("45.23")
    assert amount == 45.23
    assert currency is None


def test_with_dollar_sign():
    amount, currency = _normalize_amount_token("$1,234.56")
    assert amount == 1234.56
    assert currency == "USD"


@pytest.mark.parametrize("currency_code", ["USD", "EUR", "GBP", "INR"])
def test_explicit_currency_code_is_preserved(currency_code: str):
    amount, currency = _normalize_amount_token(f"{currency_code} 1,234.56")
    assert amount == 1234.56
    assert currency == currency_code


@pytest.mark.parametrize("token, expected_currency", [("0.00", None), ("USD 0.00", "USD")])
def test_zero_amount_preserves_currency_evidence(token: str, expected_currency: str | None):
    amount, currency = _normalize_amount_token(token)
    assert amount == 0.0
    assert currency == expected_currency


@pytest.mark.parametrize("token", ["", "   ", None])
def test_empty_amount_has_no_currency(token: str | None):
    amount, currency = _normalize_amount_token(token)
    assert amount is None
    assert currency is None


@pytest.mark.parametrize("currency_code", ["USD", "EUR", "INR"])
def test_bare_decimal_uses_document_currency(monkeypatch, currency_code: str):
    lines = ["Amazon Web Services", f"Currency: {currency_code}", "Amazon EC2 | 45.23"]
    monkeypatch.setattr(
        "app.bill_parser.pdf_parser._extract_with_pdfplumber",
        lambda content: (lines, {}),
    )

    frame, metadata = parse_pdf_invoice(b"%PDF-1.4 test", "invoice.pdf")

    assert frame["Service"].tolist() == ["Elastic Compute Cloud"]
    assert frame["Cost"].tolist() == [45.23]
    assert metadata["currency"] == currency_code


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
