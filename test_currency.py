"""
Quick smoke test for the currency detection functions.
Run: python test_currency.py
"""
import re
import pandas as pd

_CURRENCY_CODE_RE = re.compile(r"\b(USD|EUR|GBP|INR|AUD|CAD|JPY|CHF)\b", re.IGNORECASE)
_CURRENCY_COLUMN_NAMES = (
    "billingcurrency", "currency", "costinbillingcurrency",
    "currencycode", "billing_currency", "invoice_currency", "currency_code",
)


def detect_df(df):
    cols_lower = {col.strip().lower().replace(" ", ""): col for col in df.columns}
    for name in _CURRENCY_COLUMN_NAMES:
        col = cols_lower.get(name)
        if col is None:
            continue
        values = df[col].dropna().astype(str).str.strip().str.upper()
        for val in values:
            if len(val) == 3 and val.isalpha():
                return val
    cost_keywords = ("cost", "amount", "price", "charge", "spend", "total")
    sample_text = ""
    for col in df.columns:
        if any(kw in col.lower() for kw in cost_keywords):
            sample_text += " ".join(df[col].dropna().astype(str).head(30).tolist()) + " "
    if not sample_text:
        sample_text = " ".join(df.head(30).astype(str).values.flatten().tolist())
    sample_lower = sample_text.lower()
    if "\u20b9" in sample_text or "rs." in sample_lower:
        return "INR"
    if "\u20ac" in sample_text:
        return "EUR"
    if "\u00a3" in sample_text:
        return "GBP"
    m = _CURRENCY_CODE_RE.search(sample_text)
    if m:
        return m.group(1).upper()
    for col in df.columns:
        m = _CURRENCY_CODE_RE.search(col)
        if m:
            return m.group(1).upper()
    return "USD"


def detect_text(lines):
    text = " ".join(lines)
    tu = text.upper()
    if "\u20b9" in text:
        return "INR"
    if "\u20ac" in text:
        return "EUR"
    if "\u00a3" in text:
        return "GBP"
    if re.search(r"\bRS\.?\b", tu):
        return "INR"
    for code in ("INR", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY"):
        if re.search(rf"(?<![A-Z]){code}(?![A-Z])", tu):
            return code
    return "USD"


TESTS = [
    # (description, expected, actual)
    ("Azure INR BillingCurrency col",
     "INR",
     detect_df(pd.DataFrame({"BillingCurrency": ["INR", "INR"], "CostInBillingCurrency": [100.0, 200.0]}))),

    ("AWS USD default (no currency col)",
     "USD",
     detect_df(pd.DataFrame({"lineItem/UnblendedCost": [10.5], "product/ProductName": ["EC2"]}))),

    ("INR rupee symbol in cost cells",
     "INR",
     detect_df(pd.DataFrame({"Cost": ["\u20b9100.00", "\u20b9200.00"], "Service": ["EC2", "S3"]}))),

    ("EUR euro symbol in cost cells",
     "EUR",
     detect_df(pd.DataFrame({"Cost": ["\u20ac100.00", "\u20ac200.00"], "Service": ["EC2", "S3"]}))),

    ("GBP currency column",
     "GBP",
     detect_df(pd.DataFrame({"currency": ["GBP", "GBP"], "amount": [50.0, 75.0]}))),

    ("PDF INR word in text",
     "INR",
     detect_text(["Total INR 5000.00"])),

    ("PDF rupee symbol",
     "INR",
     detect_text(["\u20b95000.00 Amazon"])),

    ("PDF EUR word",
     "EUR",
     detect_text(["Total EUR 1234.56"])),

    ("PDF USD word",
     "USD",
     detect_text(["Total USD 456.78"])),

    ("PDF no cue defaults USD",
     "USD",
     detect_text(["Total 123.45 Some Bill"])),

    ("PDF Rs. marker",
     "INR",
     detect_text(["Rs. 5000.00 Total"])),

    ("BillingCurrencyCode col INR",
     "INR",
     detect_df(pd.DataFrame({"PreTaxCost": [100.0], "BillingCurrencyCode": ["INR"]}))),

    ("CAD in column header",
     "CAD",
     detect_df(pd.DataFrame({"CAD_Cost": [100.0], "Service": ["EC2"]}))),

    ("AUD text in PDF",
     "AUD",
     detect_text(["Total AUD 456.78", "Google Cloud"])),
]

failures = 0
for desc, expected, actual in TESTS:
    status = "PASS" if actual == expected else "FAIL"
    if actual != expected:
        failures += 1
    print(f"  [{status}] {desc}: expected={expected}, got={actual}")

print()
if failures:
    print(f"RESULT: {failures}/{len(TESTS)} TESTS FAILED")
else:
    print(f"RESULT: All {len(TESTS)} tests passed!")
