"""
Cloud-document domain validator.

Rejects medical, legal, academic, and other non-cloud documents
before any parsing or AI-extraction work is performed.
"""

from __future__ import annotations

import re
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Keyword banks
# ---------------------------------------------------------------------------

_DISQUALIFYING_PHRASES: list[str] = [
    # Medical / pathology
    "blood test", "blood report", "lab report", "laboratory report",
    "pathology report", "cbc report", "complete blood count", "lipid panel",
    "haemoglobin", "hemoglobin", "platelet", "wbc count", "rbc count",
    "creatinine", "urea nitrogen", "cholesterol", "triglyceride",
    "blood glucose", "serum", "plasma", "urine test", "urine analysis",
    "stool test", "x-ray report", "mri report", "ct scan report",
    "ecg report", "eeg report", "histopathology", "biopsy report",
    "radiology report", "discharge summary", "prescription",
    "patient name", "date of birth", "age/sex", "physician",
    "diagnosis", "medications", "clinical notes",
    # Academic
    "mark sheet", "marksheet", "grade card", "gradecard",
    "academic transcript", "semester result", "annual result",
    "roll number", "student name", "course name", "subject code",
    "university name", "school certificate", "passing certificate",
    # Legal
    "affidavit", "court order", "judicial", "notarized",
    "hereby declare", "power of attorney", "deed of",
    "sale deed", "rental agreement", "lease agreement",
    # HR / payroll
    "salary slip", "payslip", "pay slip", "offer letter",
    "appointment letter", "relieving letter", "experience letter",
    "employee id", "pf number", "esi number",
    # Insurance
    "insurance policy", "policy number", "insured name",
    "sum insured", "claim form", "premium paid",
    # Retail / e-commerce (non-cloud)
    "order summary", "shipping address", "delivery address",
    "product name", "quantity ordered", "return policy",
]

_CLOUD_BILL_PHRASES: list[str] = [
    "amazon web services", "aws", "microsoft azure", "google cloud",
    "gcp", "oracle cloud", "digitalocean", "linode", "vultr",
    "cloudflare", "heroku",
    "cloud bill", "cloud invoice", "usage charges", "on-demand",
    "reserved instance", "savings plan", "committed use discount",
    "spot instance", "ec2", "s3 bucket", "azure vm", "azure blob",
    "compute engine", "cloud storage", "cloud sql", "cloud run",
    "lambda function", "api gateway", "cloudwatch", "route 53",
    "virtual machine", "storage account", "bandwidth usage",
    "data transfer", "egress", "ingress", "pay-as-you-go",
    "billing period", "invoice date", "due date", "account id",
    "subscription id", "billing account", "resource group",
    "service category", "meter category", "product code",
    "usage type", "usage quantity", "blended cost", "unblended cost",
    "amortized cost",
]


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


class ValidationResult(NamedTuple):
    is_cloud_bill: bool
    rejection_reason: str | None


def validate_cloud_document(text: str) -> ValidationResult:
    """
    Classify text as a cloud-provider bill or a disqualified document.

    Scoring:
    - Each disqualifying phrase hit adds 1 to disqualify_score.
    - Each cloud-bill phrase hit adds 1 to cloud_score.
    - If disqualify_score >= 3 AND disqualify_score > cloud_score -> rejected.
    """
    normalised = _normalise(text)
    disqualify_score = sum(1 for phrase in _DISQUALIFYING_PHRASES if phrase in normalised)
    cloud_score = sum(1 for phrase in _CLOUD_BILL_PHRASES if phrase in normalised)

    if disqualify_score >= 3 and disqualify_score > cloud_score:
        matched = next(p for p in _DISQUALIFYING_PHRASES if p in normalised)
        category = _classify_disqualifier(matched)
        return ValidationResult(
            is_cloud_bill=False,
            rejection_reason=(
                f"Detected {category} (matched: '{matched}'). "
                "Please upload a cloud provider bill."
            ),
        )

    return ValidationResult(is_cloud_bill=True, rejection_reason=None)


def _classify_disqualifier(phrase: str) -> str:
    phrase_lower = phrase.lower()
    medical_tokens = {
        "blood", "lab", "pathology", "cbc", "haemo", "hemo", "platelet",
        "creatinine", "urea", "cholesterol", "triglyceride", "glucose",
        "serum", "plasma", "urine", "stool", "x-ray", "mri", "ct scan",
        "ecg", "eeg", "histopathology", "biopsy", "radiology",
        "discharge", "prescription", "patient", "physician", "diagnosis",
        "medication", "clinical",
    }
    academic_tokens = {
        "mark", "grade", "academic", "semester", "annual result",
        "roll number", "student", "course", "subject", "university",
        "school", "certificate",
    }
    legal_tokens = {
        "affidavit", "court", "judicial", "notarize", "declare",
        "attorney", "deed", "rental", "lease",
    }
    hr_tokens = {
        "salary", "payslip", "pay slip", "offer letter", "appointment",
        "relieving", "experience letter", "employee", "pf number", "esi",
    }
    insurance_tokens = {"insurance", "policy", "insured", "claim", "premium"}
    retail_tokens = {
        "order summary", "shipping", "delivery", "product name",
        "quantity ordered", "return policy",
    }

    for token in medical_tokens:
        if token in phrase_lower:
            return "medical / laboratory document"
    for token in academic_tokens:
        if token in phrase_lower:
            return "academic document"
    for token in legal_tokens:
        if token in phrase_lower:
            return "legal document"
    for token in hr_tokens:
        if token in phrase_lower:
            return "HR / payroll document"
    for token in insurance_tokens:
        if token in phrase_lower:
            return "insurance document"
    for token in retail_tokens:
        if token in phrase_lower:
            return "retail / e-commerce receipt"
    return "non-cloud document"
