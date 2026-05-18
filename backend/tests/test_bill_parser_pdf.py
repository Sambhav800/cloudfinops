import pytest
from pathlib import Path

from app.bill_parser import parse_bill


def _build_text_pdf(lines: list[str]) -> bytes:
    content_lines = [
        "BT",
        "/F1 12 Tf",
        "72 720 Td",
    ]

    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index > 0:
            content_lines.append("0 -18 Td")
        content_lines.append(f"({escaped}) Tj")

    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n"
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>\n"
            b"endobj\n"
        ),
        b"4 0 obj\n<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]

    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj

    xref_offset = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
    pdf += f"{xref_offset}\n%%EOF\n".encode("ascii")
    return pdf


def test_parse_bill_supports_text_pdf_invoice():
    pdf_bytes = _build_text_pdf(
        [
            "Amazon Web Services Invoice",
            "Amazon Elastic Compute Cloud 123.45",
            "Amazon S3 45.67",
            "Grand Total 169.12",
        ]
    )

    parsed = parse_bill(pdf_bytes, "aws-invoice.pdf")

    assert parsed["provider"] == "aws"
    assert parsed["rows_parsed"] == 2
    assert parsed["total_spend"] == 169.12
    assert parsed["currency"] == "USD"
    assert parsed["source_format"] == "pdf"
    assert parsed["source_parser"] == "pdf_invoice_parser"
    assert parsed["by_category"] == {
        "Compute": 123.45,
        "Storage": 45.67,
    }
    assert [
        {"service": row["service"], "cost": row["cost"]}
        for row in parsed["raw_services"]
    ] == [
        {"service": "Amazon Elastic Compute Cloud", "cost": 123.45},
        {"service": "Amazon S3", "cost": 45.67},
    ]
    assert parsed["raw_services"][0]["page"] == 1
    assert parsed["raw_services"][0]["line_number"] == 2
    assert parsed["raw_services"][0]["source_line"] == "Amazon Elastic Compute Cloud 123.45"
    assert parsed["source_metadata"]["line_items_detected"] == 2


def test_parse_bill_pdf_skips_summary_totals_credits_and_duplicates(monkeypatch):
    monkeypatch.setattr(
        "app.bill_parser.pdf_parser._extract_with_pdfplumber",
        lambda content: (
            [
                "Amazon Web Services India Private Limited 865.79",
                "Service provider Total in USD 1731.58",
                "Estimated grand total 865.79",
                "Total pre-tax 865.79",
                "Savings Plans Discounts Total savings (USD 206.08)",
                "Elastic Load Balancing 209.20",
                "Elastic Load Balancing 209.20",
                "Amazon Relational Database Service 171.59",
                "Virtual Private Cloud 145.17",
                "Amazon Elastic Compute Cloud 220.00",
                "Amazon Simple Storage Service 119.83",
                "865.79",
            ],
            {"extractors_used": ["pdfplumber"], "page_count": 1, "table_rows_detected": 12, "text_lines_detected": 12},
        ),
    )

    parsed = parse_bill(b"%PDF-1.4 synthetic", "aws-invoice.pdf")

    assert parsed["provider"] == "aws"
    assert parsed["rows_parsed"] == 5
    assert parsed["total_spend"] == pytest.approx(865.79)
    assert parsed["by_category"]["Load Balancing"] == pytest.approx(209.2)
    assert parsed["by_category"]["Database"] == pytest.approx(171.59)
    assert parsed["by_category"]["Networking"] == pytest.approx(145.17)
    assert "Other" not in parsed["by_category"]
    assert max(parsed["by_category"].values()) < 1000
    assert parsed["existing_credits_and_savings"] == pytest.approx(206.08)
    assert not any(row["source_line"] == "865.79" for row in parsed["raw_services"])


def test_parse_bill_pdf_keeps_aws_detail_charge_rows_without_rollup_duplicates(monkeypatch):
    monkeypatch.setattr(
        "app.bill_parser.pdf_parser._extract_with_pdfplumber",
        lambda content: (
            [
                "AWS estimated bill summary",
                "Estimated grand total: USD 1,058.01",
                "Charges by service",
                "Description Usage Quantity Amount in USD",
                "Elastic Compute Cloud USD 950.00",
                "Asia Pacific (Mumbai) USD 950.00",
                "Amazon Elastic Compute Cloud running Red Hat Enterprise Linux USD 450.00",
                "$0.30 per On Demand RHEL c5a.2xlarge Instance Hour 1,500 Hrs USD 450.00",
                "EBS USD 500.00",
                "$0.10 per GB-month of General Purpose SSD (gp2) provisioned storage - Asia Pacific 5,000 GB-Mo USD 500.00",
                "Data Transfer USD 103.30",
                "Asia Pacific (Mumbai) USD 103.30",
                "Bandwidth USD 103.30",
                "$0.1093 per GB - first 10 TB / month data transfer out beyond the global free tier 944.19 GB USD 103.30",
                "CloudWatch USD 4.71",
                "AmazonCloudWatch DashboardHour USD 2.42",
                "$3.00 per Dashboard per Month 0.806 Dashboards USD 2.42",
                "Amazon CloudWatch USD 2.29",
                "$0.10 per alarm metric month (standard resolution) - Asia Pacific (Mumbai) 2 Alarms USD 0.20",
                "$0.30 per metric-month for the first 10,000 metrics - Asia Pacific (Mumbai) 6.961 Metrics USD 2.09",
            ],
            {"extractors_used": ["pdfplumber"], "page_count": 1, "table_rows_detected": 0, "text_lines_detected": 20},
        ),
    )

    parsed = parse_bill(b"%PDF-1.4 synthetic", "aws-invoice.pdf")

    service_names = [row["service"] for row in parsed["raw_services"]]
    assert parsed["rows_parsed"] == 6
    assert parsed["total_spend"] == pytest.approx(1058.01)
    assert sum(row["cost"] for row in parsed["raw_services"]) == pytest.approx(1058.01)
    assert parsed["existing_credits_and_savings"] == 0
    assert not any(name == "Asia Pacific" for name in service_names)
    assert not any(name == "CloudWatch" for name in service_names)
    assert any("On Demand RHEL c5a.2xlarge" in name for name in service_names)
    assert any("General Purpose SSD" in name for name in service_names)
    assert any("beyond the global free tier" in name for name in service_names)


def test_uploaded_aws_pdf_parses_expected_line_count_and_total():
    bill_path = Path("/Users/nishantjain/Downloads/aws_20260310_124549_69b0127dbda0c.pdf")
    if not bill_path.exists():
        pytest.skip("reference AWS PDF is not available on this machine")

    parsed = parse_bill(bill_path.read_bytes(), bill_path.name)

    assert parsed["rows_parsed"] == 99
    assert parsed["total_spend"] == pytest.approx(4246.66)
