import zlib

import pytest

from app.bill_parser import parse_bill


def _build_text_pdf(lines: list[str]) -> bytes:
    escaped_lines = [
        line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        for line in lines
    ]

    stream_parts = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(escaped_lines):
        if index > 0:
            stream_parts.append("0 -18 Td")
        stream_parts.append(f"({line}) Tj")
    stream_parts.append("ET")

    compressed_stream = zlib.compress("\n".join(stream_parts).encode("latin-1"))
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
            b"endobj\n"
        ),
        (
            f"4 0 obj\n<< /Length {len(compressed_stream)} /Filter /FlateDecode >>\nstream\n".encode("latin-1")
            + compressed_stream
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    output = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0]
    current_length = len(output[0])

    for obj in objects:
        offsets.append(current_length)
        output.append(obj)
        current_length += len(obj)

    xref_offset = current_length
    xref_lines = [b"xref\n", f"0 {len(offsets)}\n".encode("latin-1"), b"0000000000 65535 f \n"]
    xref_lines.extend(f"{offset:010d} 00000 n \n".encode("latin-1") for offset in offsets[1:])
    xref_lines.extend(
        [
            b"trailer\n",
            f"<< /Size {len(offsets)} /Root 1 0 R >>\n".encode("latin-1"),
            b"startxref\n",
            f"{xref_offset}\n".encode("latin-1"),
            b"%%EOF",
        ]
    )
    output.extend(xref_lines)

    return b"".join(output)


def test_parse_bill_parses_text_pdf_into_normalized_payload(monkeypatch):
    monkeypatch.setattr(
        "app.bill_parser.pdf_parser._extract_with_pdfplumber",
        lambda content: (
            [],
            {"extractors_used": [], "page_count": 0, "table_rows_detected": 0, "text_lines_detected": 0},
        ),
    )
    pdf_bytes = _build_text_pdf(
        [
            "Amazon Web Services Invoice",
            "Amazon EC2    USD 120.50",
            "Amazon S3    USD 40.25",
            "CloudFront    USD 19.25",
            "Total    USD 180.00",
        ]
    )

    parsed = parse_bill(pdf_bytes, "aws-invoice.pdf")

    assert parsed["provider"] == "aws"
    assert parsed["rows_parsed"] == 3
    assert parsed["total_spend"] == pytest.approx(180.0)
    assert parsed["currency"] == "USD"
    assert parsed["by_category"] == {
        "Compute": 120.5,
        "Storage": 40.25,
        "CDN": 19.25,
    }
    assert parsed["source_format"] == "pdf"
    assert parsed["source_parser"] == "pdf_invoice_parser"
    assert parsed["source_metadata"]["line_items_detected"] == 3
    assert parsed["source_metadata"]["provider_hint"] == "aws"


def test_parse_bill_pdf_without_service_level_rows_raises_value_error(monkeypatch):
    monkeypatch.setattr(
        "app.bill_parser.pdf_parser._extract_with_pdfplumber",
        lambda content: (
            [],
            {"extractors_used": [], "page_count": 0, "table_rows_detected": 0, "text_lines_detected": 0},
        ),
    )
    pdf_bytes = _build_text_pdf(
        [
            "Amazon Web Services Invoice",
            "Billing period March 2026",
            "Invoice number 123456789",
            "Total USD 180.00",
        ]
    )

    with pytest.raises(ValueError, match="service-level charges"):
        parse_bill(pdf_bytes, "aws-summary.pdf")


def test_parse_bill_pdf_without_extractable_text_raises_clear_error(monkeypatch):
    monkeypatch.setattr(
        "app.bill_parser.pdf_parser._extract_with_pdfplumber",
        lambda content: (
            [],
            {"extractors_used": [], "page_count": 0, "table_rows_detected": 0, "text_lines_detected": 0},
        ),
    )

    with pytest.raises(ValueError, match="Could not extract readable text from this PDF invoice"):
        parse_bill(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF", "opaque.pdf")


def test_parse_bill_csv_keeps_negative_credit_rows_in_net_total():
    """Credits/refunds must stay in the net bill total instead of being dropped."""
    csv_bytes = (
        b"Service,Cost\n"
        b"Amazon EC2,100\n"
        b"Amazon S3,50\n"
        b"Credits,-20\n"
    )

    parsed = parse_bill(csv_bytes, "aws-credits.csv")

    assert parsed["provider"] == "aws"
    assert parsed["total_spend"] == pytest.approx(130.0)
    assert parsed["existing_credits_and_savings"] == pytest.approx(20.0)
    assert parsed["by_category"] == {
        "Compute": 100.0,
        "Storage": 50.0,
    }


def test_parse_bill_csv_positive_rows_keep_positive_total():
    csv_bytes = (
        b"Service,Cost\n"
        b"Amazon EC2,100\n"
        b"Amazon S3,50\n"
    )

    parsed = parse_bill(csv_bytes, "aws-positive.csv")

    assert parsed["provider"] == "aws"
    assert parsed["total_spend"] == pytest.approx(150.0)
    assert parsed["existing_credits_and_savings"] == pytest.approx(0.0)
    assert parsed["by_category"] == {
        "Compute": 100.0,
        "Storage": 50.0,
    }


def test_parse_bill_csv_preserves_all_service_rollups_for_large_bills():
    rows = ["Service,Cost,Usage Type"]
    rows.extend(f"Custom Service {index},{index + 1},On-Demand" for index in range(30))
    csv_bytes = ("\n".join(rows) + "\n").encode("utf-8")

    parsed = parse_bill(csv_bytes, "aws-large-bill.csv")

    assert parsed["rows_parsed"] == 30
    assert parsed["total_spend"] == pytest.approx(sum(range(1, 31)))
    assert len(parsed["raw_services"]) == 30
    assert parsed["raw_services"][0] == {"service": "Custom Service 29", "cost": 30.0}
    assert parsed["raw_services"][-1] == {"service": "Custom Service 0", "cost": 1.0}


def test_parse_bill_csv_zero_only_rows_raise_no_billable_costs():
    csv_bytes = (
        b"Service,Cost\n"
        b"Amazon EC2,0\n"
    )

    with pytest.raises(ValueError, match="No billable costs were found in this file."):
        parse_bill(csv_bytes, "aws-zero.csv")
