"""
Comprehensive validation and trust test suite for CloudFinOps bill scanner.

Ensures that:
1. Medical reports, pathology/blood tests, academic, legal, and HR documents are rejected (422).
2. Generic non-cloud invoices (consulting, office supplies, etc.) with no cloud evidence are rejected (422).
3. Empty, whitespace-only, and unreadable PDFs (< 5 words) are rejected (422).
4. Renamed files (e.g., medical CSV renamed to aws-bill.csv) cannot bypass validation (422).
5. Valid AWS, Azure, and GCP bills (CSV and PDF) pass validation and return 200.
6. Public route (/api/scan/public-upload) returns 422 for invalid documents and never returns teasers or savings estimates.
7. Authenticated route (/api/scan/upload-bill) returns 422 for invalid documents and never persists analyses to the database.
8. Gemini direct extraction fallback is never triggered for domain rejections.
"""

from __future__ import annotations

import asyncio
from typing import Any
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.routes import router
from app.auth import ClerkUser, get_current_user
from app.bill_parser.validator import validate_cloud_document, ValidationResult
from app.db import get_db_client


# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------

BLOOD_TEST_TEXT = (
    "Patient Name: John Doe  DOB: 1985-05-12  Age/Sex: 41/M  "
    "Complete Blood Count (CBC) Report  "
    "Haemoglobin: 14.2 g/dL  Platelet count: 240,000 /mcL  "
    "WBC count: 6,800 /mcL  RBC count: 4.9 million/mcL  "
    "Physician: Dr. Sarah Connor  Diagnosis: Normal  Prescription: None"
)

GENERIC_INVOICE_TEXT = (
    "Acme Business Consulting LLC  "
    "Invoice Number: INV-2026-9041  "
    "Invoice Date: 2026-03-15  Due Date: 2026-04-15  "
    "Description: Strategic Advisory and Architecture Review  "
    "Hours: 20  Hourly Rate: 150.00  Total Amount: 3000.00"
)

EMPTY_TEXT = "   \n\t  "
SHORT_UNREADABLE_TEXT = "Page 1 scan error"

AWS_VALID_TEXT = (
    "lineItem/ProductCode,lineItem/UsageType,lineItem/BlendedCost,lineItem/UnblendedCost,lineItem/LineItemDescription\n"
    "AmazonEC2,BoxUsage:t3.medium,45.20,45.20,t3.medium compute hours in us-east-1\n"
    "AmazonS3,TimedStorage-ByteHrs,12.50,12.50,Standard storage in us-east-1\n"
    "AWSDataTransfer,DataTransfer-Out-Bytes,8.10,8.10,Bandwidth usage egress\n"
)

AZURE_VALID_TEXT = (
    "SubscriptionId,ResourceGroup,MeterCategory,CostInBillingCurrency,ResourceRate,ProductName\n"
    "sub-1234-abcd,rg-production,Virtual Machines,85.50,1.20,Microsoft Azure Virtual Machine\n"
    "sub-1234-abcd,rg-production,Storage Account,24.00,0.40,Microsoft Azure Blob Storage\n"
)

GCP_VALID_TEXT = (
    "Billing Account ID,Project ID,Service Description,Cost,Usage Type\n"
    "0123-4567-89AB,my-cloud-app,Google Cloud Compute Engine,65.00,Commitment vCPU\n"
    "0123-4567-89AB,my-cloud-app,Google Cloud Storage,18.50,Standard Cloud Storage\n"
)

MEDICAL_CSV_CONTENT = (
    "Patient Name,Date of Birth,Test Name,Result,Reference Range\n"
    "John Doe,1985-05-12,Complete Blood Count,Normal,Normal\n"
    "John Doe,1985-05-12,Haemoglobin,14.2 g/dL,12-16\n"
    "John Doe,1985-05-12,Platelet count,240000,150000-450000\n"
    "John Doe,1985-05-12,WBC count,6800,4000-11000\n"
).encode("utf-8")

GENERIC_INVOICE_CSV_CONTENT = (
    "Invoice Number,Vendor Name,Description,Quantity,Unit Price,Total\n"
    "INV-2026-9041,Acme Office Supplies,Ergonomic Office Chair,4,250.00,1000.00\n"
    "INV-2026-9041,Acme Office Supplies,Standing Desk Converter,2,300.00,600.00\n"
).encode("utf-8")


class FakeBillAnalysisDB:
    def __init__(self):
        self.analyses: list[dict[str, Any]] = []
        self.user_features: list[dict[str, Any]] = []

    async def create_bill_analysis(self, analysis: dict[str, Any]) -> dict[str, Any]:
        row = {
            "id": f"analysis-{len(self.analyses) + 1}",
            "created_at": "2026-03-21T10:00:00+00:00",
            **analysis,
        }
        self.analyses.append(row)
        return row

    async def get_latest_bill_analysis(self, user_id: str) -> dict[str, Any] | None:
        matches = [row for row in self.analyses if row.get("user_id") == user_id]
        return matches[-1] if matches else None

    async def get_bill_analyses(self, user_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
        matches = [row for row in self.analyses if row.get("user_id") == user_id]
        matches.sort(key=lambda row: row.get("created_at") or "", reverse=True)
        return matches[:limit]

    async def get_bill_analysis(self, user_id: str, analysis_id: str) -> dict[str, Any] | None:
        for row in self.analyses:
            if row.get("user_id") == user_id and row.get("id") == analysis_id:
                return row
        return None

    async def mark_user_feature_enabled(self, user_id: str, feature: str, *, last_used=None, first_upload_at=None):
        row = {
            "id": f"feature-{len(self.user_features) + 1}",
            "user_id": user_id,
            "feature": feature,
            "enabled": True,
            "last_used": last_used,
            "first_upload_at": first_upload_at or last_used,
        }
        self.user_features.append(row)
        return row

    async def update(self, table: str, data: dict[str, Any], filters: dict[str, Any]):
        assert table == "bill_analyses"
        updated = []
        for row in self.analyses:
            if all(row.get(key) == value for key, value in filters.items()):
                row.update(data)
                updated.append(row)
        return updated


def _build_client(fake_db: FakeBillAnalysisDB) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: ClerkUser(id="user-val-1")
    app.dependency_overrides[get_db_client] = lambda: fake_db
    return TestClient(app)


@pytest.fixture(autouse=True)
def _stub_external_services(monkeypatch):
    """Stub Gemini and GCS services to keep tests offline and deterministic."""
    async def _fake_extract_bill_with_gemini(content, filename, *, content_type=None):
        return None

    async def _fake_enrich_with_gemini(parsed, content, filename, *, content_type=None):
        return parsed

    async def _fake_fetch_prices(**kwargs):
        return []

    async def _fake_arbitrage(**kwargs):
        return []

    async def _fake_exec_report(**kwargs):
        return {
            "headline": "AWS Cost Intelligence",
            "findings": [],
            "quick_wins": [],
            "roadmap": [],
            "cross_cloud_comparison": [],
            "client_scripts": {},
            "verification_status": "source_grounded_unverified_savings",
            "additional_savings_max": 0.0,
        }

    async def _fake_archive(**kwargs):
        return {
            "storage_provider": "gcs",
            "status": "stored",
            "original_filename": kwargs["filename"],
            "content_type": kwargs["content_type"] or "application/octet-stream",
            "size_bytes": len(kwargs["content"]),
            "sha256": kwargs["content_hash"],
            "bucket": "cloudfinops-bill-uploads",
            "object_path": f"bill-uploads/user-val-1/mock-{kwargs['filename']}",
            "stored_at": "2026-03-21T10:00:00+00:00",
        }

    monkeypatch.setattr("app.bill_parser.extract_bill_with_gemini", _fake_extract_bill_with_gemini)
    monkeypatch.setattr("app.bill_parser.enrich_parsed_bill_with_gemini", _fake_enrich_with_gemini)
    monkeypatch.setattr("app.bill_parser.fetch_cross_cloud_prices", _fake_fetch_prices)
    monkeypatch.setattr("app.bill_parser.analyze_arbitrage", _fake_arbitrage)
    monkeypatch.setattr("app.bill_parser.generate_full_intelligence_report", _fake_exec_report)
    monkeypatch.setattr("app.api.routes.archive_uploaded_bill_to_gcs", _fake_archive)
    monkeypatch.setattr("app.api.routes._check_rate_limit", lambda ip: True)


# ===========================================================================
# 1. Validator Unit Tests
# ===========================================================================

class TestValidatorDomainChecks:
    def test_medical_report_rejected_by_validator(self):
        """Blood test and laboratory document text must be rejected with medical category."""
        result = validate_cloud_document(BLOOD_TEST_TEXT)
        assert result.is_cloud_bill is False
        assert result.rejection_reason is not None
        assert "medical" in result.rejection_reason.lower() or "laboratory" in result.rejection_reason.lower()

    def test_generic_invoice_no_cloud_evidence_rejected(self):
        """Generic business invoices with zero cloud billing terms must be rejected."""
        result = validate_cloud_document(GENERIC_INVOICE_TEXT)
        assert result.is_cloud_bill is False
        assert result.rejection_reason is not None
        assert "no cloud billing evidence" in result.rejection_reason.lower()

    def test_empty_text_rejected(self):
        """Empty or whitespace strings must be rejected immediately."""
        result = validate_cloud_document(EMPTY_TEXT)
        assert result.is_cloud_bill is False
        assert result.rejection_reason is not None
        assert "empty or unreadable" in result.rejection_reason.lower()

    def test_short_unreadable_text_rejected(self):
        """Documents with fewer than 5 words cannot establish cloud billing evidence."""
        result = validate_cloud_document(SHORT_UNREADABLE_TEXT)
        assert result.is_cloud_bill is False
        assert result.rejection_reason is not None
        assert "empty or unreadable" in result.rejection_reason.lower()

    def test_valid_aws_bill_accepted(self):
        """AWS CUR bill text with positive cloud evidence must pass."""
        result = validate_cloud_document(AWS_VALID_TEXT)
        assert result.is_cloud_bill is True
        assert result.rejection_reason is None

    def test_valid_azure_bill_accepted(self):
        """Azure billing export text with positive cloud evidence must pass."""
        result = validate_cloud_document(AZURE_VALID_TEXT)
        assert result.is_cloud_bill is True
        assert result.rejection_reason is None

    def test_valid_gcp_bill_accepted(self):
        """GCP billing export text with positive cloud evidence must pass."""
        result = validate_cloud_document(GCP_VALID_TEXT)
        assert result.is_cloud_bill is True
        assert result.rejection_reason is None


# ===========================================================================
# 2. Public Upload Route Enforcement (/api/scan/public-upload)
# ===========================================================================

class TestPublicUploadRouteValidation:
    def test_public_upload_rejects_medical_report_pdf(self, monkeypatch):
        """A blood test PDF uploaded to public scanner returns 422 with zero analysis generated."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        # Mock pdfplumber extraction to simulate blood test text
        monkeypatch.setattr(
            "app.bill_parser.pdf_parser._extract_with_pdfplumber",
            lambda content: (
                [
                    "Metropolis Diagnostic Centre - Blood Test Lab Report",
                    "Patient Name: Jane Doe  Age: 32  Sex: F",
                    "Complete Blood Count  Haemoglobin: 13.8 g/dL",
                    "Platelet Count: 280,000 /mcL  WBC Count: 7,200 /mcL",
                    "Physician: Dr. Adams  Diagnosis: Routine Health Checkup",
                ],
                {"extractors_used": ["pdfplumber"], "page_count": 1},
            ),
        )

        response = client.post(
            "/api/scan/public-upload",
            files={"file": ("blood-test-report.pdf", b"%PDF-1.4 mock medical", "application/pdf")},
        )

        assert response.status_code == 422
        detail = response.json().get("detail", "")
        assert "medical" in detail.lower() or "laboratory" in detail.lower() or "cloud provider bill" in detail.lower()
        # Verify no analysis teaser fields were returned
        assert "top_findings_teaser" not in response.json()
        assert "waste_grade" not in response.json()
        assert "total_analyzed_spend" not in response.json()
        assert "estimated_monthly_savings_min" not in response.json()

    def test_public_upload_rejects_medical_report_csv(self):
        """A medical CSV uploaded to public scanner returns 422."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/public-upload",
            files={"file": ("lab_report.csv", MEDICAL_CSV_CONTENT, "text/csv")},
        )

        assert response.status_code == 422
        detail = response.json().get("detail", "")
        assert "medical" in detail.lower() or "laboratory" in detail.lower() or "cloud provider bill" in detail.lower()

    def test_public_upload_rejects_generic_invoice_pdf(self, monkeypatch):
        """A non-cloud consulting invoice PDF returns 422 and no teaser analysis."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        monkeypatch.setattr(
            "app.bill_parser.pdf_parser._extract_with_pdfplumber",
            lambda content: (
                [
                    "Acme Management Consulting Services",
                    "Invoice Date: 2026-03-01  Due Date: 2026-03-31",
                    "Consulting Service Hours 1500.00",
                    "Client Workshop Facilitation 500.00",
                    "Total Balance Due: 2000.00",
                ],
                {"extractors_used": ["pdfplumber"], "page_count": 1},
            ),
        )

        response = client.post(
            "/api/scan/public-upload",
            files={"file": ("invoice-acme.pdf", b"%PDF-1.4 mock acme", "application/pdf")},
        )

        assert response.status_code == 422
        assert "no cloud billing evidence" in response.json().get("detail", "").lower()

    def test_public_upload_rejects_generic_invoice_csv(self):
        """A non-cloud CSV invoice returns 422."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/public-upload",
            files={"file": ("office_supplies.csv", GENERIC_INVOICE_CSV_CONTENT, "text/csv")},
        )

        assert response.status_code == 422
        assert "no cloud billing evidence" in response.json().get("detail", "").lower()

    def test_public_upload_rejects_empty_unreadable_pdf(self, monkeypatch):
        """An empty or unreadable PDF returns 422."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        monkeypatch.setattr(
            "app.bill_parser.pdf_parser._extract_with_pdfplumber",
            lambda content: (
                ["Page 1 blank"],
                {"extractors_used": ["pdfplumber"], "page_count": 1},
            ),
        )

        response = client.post(
            "/api/scan/public-upload",
            files={"file": ("blank.pdf", b"%PDF-1.4 blank", "application/pdf")},
        )

        assert response.status_code == 422
        assert "empty or unreadable" in response.json().get("detail", "").lower()

    def test_public_upload_rejects_renamed_blood_test_as_aws_csv(self):
        """A blood test CSV renamed to 'aws-bill-2026.csv' must still be rejected (422)."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/public-upload",
            files={"file": ("aws-bill-2026.csv", MEDICAL_CSV_CONTENT, "text/csv")},
        )

        assert response.status_code == 422
        assert "top_findings" not in response.json()

    def test_public_upload_accepts_valid_aws_bill(self):
        """A valid AWS CUR CSV passes public scan and returns teaser analysis."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/public-upload",
            files={"file": ("aws-cur.csv", AWS_VALID_TEXT.encode("utf-8"), "text/csv")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider_detected"].upper() == "AWS"
        assert payload["total_analyzed_spend"] > 0
        assert payload["waste_grade"] in {"A", "B", "C", "D", "F"}
        assert "estimated_monthly_savings_min" in payload
        assert "top_findings_teaser" in payload

    def test_public_upload_accepts_valid_azure_bill(self):
        """A valid Azure CSV passes public scan and returns teaser analysis."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/public-upload",
            files={"file": ("azure-export.csv", AZURE_VALID_TEXT.encode("utf-8"), "text/csv")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider_detected"].upper() == "AZURE"
        assert payload["total_analyzed_spend"] > 0
        assert "top_findings_teaser" in payload

    def test_public_upload_accepts_valid_gcp_bill(self):
        """A valid GCP CSV passes public scan and returns teaser analysis."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/public-upload",
            files={"file": ("gcp-export.csv", GCP_VALID_TEXT.encode("utf-8"), "text/csv")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider_detected"].upper() == "GCP"
        assert payload["total_analyzed_spend"] > 0
        assert "top_findings_teaser" in payload


# ===========================================================================
# 3. Authenticated Upload Route Enforcement (/api/scan/upload-bill)
# ===========================================================================

class TestAuthenticatedUploadRouteValidation:
    def test_authenticated_upload_rejects_medical_report_pdf_and_never_persists(self, monkeypatch):
        """A blood test PDF to authenticated upload returns 422 and is never stored in DB."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        monkeypatch.setattr(
            "app.bill_parser.pdf_parser._extract_with_pdfplumber",
            lambda content: (
                [
                    "Pathology Lab Blood Report",
                    "Patient Name: Robert Paulson  Age/Sex: 45/M",
                    "Complete Blood Count  Platelet count: 210,000",
                    "Haemoglobin: 15.1 g/dL  Clinical Notes: Normal",
                ],
                {"extractors_used": ["pdfplumber"], "page_count": 1},
            ),
        )

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("blood-test.pdf", b"%PDF-1.4 blood test", "application/pdf")},
        )

        assert response.status_code == 422
        # CRITICAL TRUST ASSERTION: Database MUST remain completely empty
        assert len(fake_db.analyses) == 0

    def test_authenticated_upload_rejects_medical_report_csv(self):
        """A medical CSV to authenticated upload returns 422 and does not persist."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("patient_tests.csv", MEDICAL_CSV_CONTENT, "text/csv")},
        )

        assert response.status_code == 422
        assert len(fake_db.analyses) == 0

    def test_authenticated_upload_rejects_generic_invoice_pdf(self, monkeypatch):
        """A consulting invoice PDF to authenticated route returns 422 and does not persist."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        monkeypatch.setattr(
            "app.bill_parser.pdf_parser._extract_with_pdfplumber",
            lambda content: (
                [
                    "Apex Software Consulting Services",
                    "Invoice Date: 2026-03-10  Due Date: 2026-04-10",
                    "Senior Engineering Hours 2400.00",
                    "Total: 2400.00",
                ],
                {"extractors_used": ["pdfplumber"], "page_count": 1},
            ),
        )

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("consulting-bill.pdf", b"%PDF-1.4 consulting", "application/pdf")},
        )

        assert response.status_code == 422
        assert len(fake_db.analyses) == 0

    def test_authenticated_upload_rejects_generic_invoice_csv(self):
        """A generic invoice CSV to authenticated route returns 422 and does not persist."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("office_expenses.csv", GENERIC_INVOICE_CSV_CONTENT, "text/csv")},
        )

        assert response.status_code == 422
        assert len(fake_db.analyses) == 0

    def test_authenticated_upload_rejects_empty_unreadable_pdf(self, monkeypatch):
        """An empty PDF to authenticated route returns 422 and does not persist."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        monkeypatch.setattr(
            "app.bill_parser.pdf_parser._extract_with_pdfplumber",
            lambda content: (
                ["Blank document"],
                {"extractors_used": ["pdfplumber"], "page_count": 1},
            ),
        )

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("blank.pdf", b"%PDF-1.4 blank", "application/pdf")},
        )

        assert response.status_code == 422
        assert len(fake_db.analyses) == 0

    def test_authenticated_upload_rejects_renamed_file(self):
        """Medical report renamed to 'aws-cur-march2026.csv' returns 422 and does not persist."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("aws-cur-march2026.csv", MEDICAL_CSV_CONTENT, "text/csv")},
        )

        assert response.status_code == 422
        assert len(fake_db.analyses) == 0

    def test_authenticated_upload_accepts_valid_aws_bill(self):
        """Valid AWS bill CSV returns 200 and is persisted into DB."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("aws-billing.csv", AWS_VALID_TEXT.encode("utf-8"), "text/csv")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "aws"
        assert payload["total_analyzed_spend"] > 0
        assert len(fake_db.analyses) == 1
        assert fake_db.analyses[0]["provider"] == "aws"

    def test_authenticated_upload_accepts_valid_azure_bill(self):
        """Valid Azure bill CSV returns 200 and is persisted into DB."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("azure-cost.csv", AZURE_VALID_TEXT.encode("utf-8"), "text/csv")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "azure"
        assert len(fake_db.analyses) == 1
        assert fake_db.analyses[0]["provider"] == "azure"

    def test_authenticated_upload_accepts_valid_gcp_bill(self):
        """Valid GCP bill CSV returns 200 and is persisted into DB."""
        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("gcp-export.csv", GCP_VALID_TEXT.encode("utf-8"), "text/csv")},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "gcp"
        assert len(fake_db.analyses) == 1
        assert fake_db.analyses[0]["provider"] == "gcp"


# ===========================================================================
# 4. Gemini Direct Extraction Guard Test
# ===========================================================================

class TestGeminiDirectExtractionGuard:
    def test_gemini_fallback_blocked_for_domain_rejection(self, monkeypatch):
        """
        When a non-cloud file (e.g. medical report) is uploaded, the parser throws a domain rejection.
        _try_gemini_direct_extraction must NEVER be invoked to prevent Gemini from resurrecting
        or hallucinating savings on disqualified documents.
        """
        gemini_called = []

        async def _tracking_gemini_extract(content, filename, *, content_type=None):
            gemini_called.append(filename)
            # If Gemini were called, it might hallucinate a valid bill response
            return {
                "provider": "aws",
                "rows_parsed": 5,
                "total_spend": 500.0,
                "currency": "USD",
                "by_category": {"Compute": 500.0},
                "raw_services": [{"service": "Amazon EC2", "cost": 500.0}],
            }

        monkeypatch.setattr("app.bill_parser.extract_bill_with_gemini", _tracking_gemini_extract)

        fake_db = FakeBillAnalysisDB()
        client = _build_client(fake_db)

        response = client.post(
            "/api/scan/upload-bill",
            files={"file": ("blood-test.csv", MEDICAL_CSV_CONTENT, "text/csv")},
        )

        # Must be rejected with 422
        assert response.status_code == 422
        # Gemini must NEVER have been called
        assert len(gemini_called) == 0, f"Gemini extraction was unexpectedly called for: {gemini_called}"
        # DB must not have any saved analyses
        assert len(fake_db.analyses) == 0
