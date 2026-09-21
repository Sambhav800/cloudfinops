"""
Unit tests for backend/app/bill_parser/validator.py

Covers:
- Cloud bills → accepted
- Medical/lab reports → rejected
- Academic transcripts → rejected
- Legal documents → rejected
- HR / payroll documents → rejected
- Mixed (cloud + mild medical noise) → accepted (cloud wins)
- Score just below threshold → accepted
"""

import pytest

from app.bill_parser.validator import validate_cloud_document, ValidationResult


# ---------------------------------------------------------------------------
# Cloud bills — must be accepted
# ---------------------------------------------------------------------------

class TestCloudBillsAccepted:
    def test_aws_csv_headers(self):
        text = (
            "billing period, account id, usage type, blended cost, "
            "amazon web services, ec2, s3 bucket, data transfer"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is True
        assert result.rejection_reason is None

    def test_azure_cost_export(self):
        text = (
            "subscription id, resource group, meter category, billing period, "
            "microsoft azure, virtual machine, storage account, amortized cost"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is True

    def test_gcp_billing_export(self):
        text = (
            "google cloud, cloud storage, compute engine, cloud sql, "
            "usage type, usage quantity, invoice date, billing account"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is True

    def test_short_cloud_text_with_few_hits(self):
        """Below-threshold disqualifiers do not block a cloud bill."""
        text = "AWS EC2 invoice for compute engine usage"
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is True

    def test_empty_text_passes(self):
        """Empty / whitespace-only text has no disqualifiers and must pass."""
        result = validate_cloud_document("")
        assert result.is_cloud_bill is True


# ---------------------------------------------------------------------------
# Medical / lab documents — must be rejected
# ---------------------------------------------------------------------------

class TestMedicalDocumentsRejected:
    def test_blood_test_report(self):
        text = (
            "patient name: John Doe  date of birth: 01-Jan-1990  age/sex: 34/M  "
            "blood test: haemoglobin 13.5 g/dL  blood glucose 98 mg/dL  "
            "physician: Dr. Smith  diagnosis: normal  prescription: none"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False
        assert result.rejection_reason is not None
        assert "medical" in result.rejection_reason.lower() or "laboratory" in result.rejection_reason.lower()

    def test_cbc_report(self):
        text = (
            "complete blood count  wbc count 6.2  rbc count 4.8  "
            "platelet 2.5 lakh  haemoglobin 13.0  clinical notes: normal"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False

    def test_radiology_report(self):
        text = (
            "radiology report  patient name: Jane Doe  "
            "mri report: no abnormality detected  physician: Dr. Rao  "
            "diagnosis: clear  medications: paracetamol"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False

    def test_discharge_summary(self):
        text = (
            "discharge summary  patient name: XYZ  age/sex: 55/F  "
            "diagnosis: hypertension  prescription: amlodipine 5mg  "
            "clinical notes: stable  physician: Dr. Kumar"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False


# ---------------------------------------------------------------------------
# Academic documents — must be rejected
# ---------------------------------------------------------------------------

class TestAcademicDocumentsRejected:
    def test_marksheet(self):
        text = (
            "mark sheet  student name: Rahul Sharma  roll number: 2021CS001  "
            "course name: B.Tech Computer Science  semester result: 8.7 CGPA  "
            "university name: IIT Delhi"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False

    def test_academic_transcript(self):
        text = (
            "academic transcript  annual result: first class  "
            "subject code: CS101  grade card: A  university name: Mumbai University"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False


# ---------------------------------------------------------------------------
# Legal documents — must be rejected
# ---------------------------------------------------------------------------

class TestLegalDocumentsRejected:
    def test_affidavit(self):
        text = (
            "affidavit  I hereby declare that the above information is true  "
            "notarized  judicial stamp  power of attorney"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False

    def test_sale_deed(self):
        text = (
            "sale deed  rental agreement  lease agreement  "
            "court order  hereby declare  judicial registration"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False


# ---------------------------------------------------------------------------
# HR / payroll documents — must be rejected
# ---------------------------------------------------------------------------

class TestHRDocumentsRejected:
    def test_salary_slip(self):
        text = (
            "salary slip  employee id: EMP001  pf number: MH/BAN/12345  "
            "esi number: 31-00-123456-000-0001  offer letter month: September 2026"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False


# ---------------------------------------------------------------------------
# Mixed signals — cloud must win when score is higher
# ---------------------------------------------------------------------------

class TestMixedSignals:
    def test_cloud_beats_mild_medical_noise(self):
        """A cloud bill that incidentally contains the word 'diagnosis' should pass."""
        text = (
            "amazon web services  billing period  account id  usage type  "
            "blended cost  ec2  s3 bucket  data transfer  invoice date  "
            "diagnosis field not found"  # one disqualifier, many cloud hits
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is True

    def test_two_disqualifiers_without_meeting_threshold(self):
        """2 disqualifier hits (< 3) must not trigger rejection."""
        text = "blood test result: patient serum checked"
        result = validate_cloud_document(text)
        # 2 hits: "blood test", "serum" — threshold is 3 — must pass
        assert result.is_cloud_bill is True


# ---------------------------------------------------------------------------
# Return shape
# ---------------------------------------------------------------------------

class TestReturnShape:
    def test_result_is_named_tuple(self):
        result = validate_cloud_document("aws billing period")
        assert isinstance(result, ValidationResult)

    def test_rejection_contains_reason(self):
        text = (
            "blood test haemoglobin platelet patient name physician diagnosis"
        )
        result = validate_cloud_document(text)
        assert result.is_cloud_bill is False
        assert isinstance(result.rejection_reason, str)
        assert len(result.rejection_reason) > 10
