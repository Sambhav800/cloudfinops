"""
Tests for BigQuery storage_path validation in _validate_gcp_automated_sync.

Ensures SQL injection via backtick-escape or special characters is blocked.
"""

import pytest
from fastapi import HTTPException

from app.api.routes import _validate_gcp_automated_sync


class TestGcpStoragePathValidation:
    """Validates that storage_path is strictly sanitized before query interpolation."""

    def test_rejects_backtick_injection(self):
        malicious_path = "project.dataset.table` WHERE 1=1; DROP TABLE `other"
        with pytest.raises(HTTPException) as exc_info:
            _validate_gcp_automated_sync(malicious_path, "{}")
        assert exc_info.value.status_code == 400
        assert "invalid characters" in exc_info.value.detail

    def test_rejects_semicolon_injection(self):
        malicious_path = "project.dataset.table;DROP TABLE foo"
        with pytest.raises(HTTPException) as exc_info:
            _validate_gcp_automated_sync(malicious_path, "{}")
        assert exc_info.value.status_code == 400

    def test_rejects_spaces_in_path(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_gcp_automated_sync("project.dataset.my table", "{}")
        assert exc_info.value.status_code == 400
        assert "invalid characters" in exc_info.value.detail

    def test_rejects_quotes_in_path(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_gcp_automated_sync('project.dataset."table"', "{}")
        assert exc_info.value.status_code == 400

    def test_rejects_wrong_segment_count(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_gcp_automated_sync("project.dataset", "{}")
        assert exc_info.value.status_code == 400
        assert "project.dataset.table" in exc_info.value.detail

    def test_rejects_empty_segment(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_gcp_automated_sync("project..table", "{}")
        assert exc_info.value.status_code == 400
        assert "invalid characters" in exc_info.value.detail

    def test_accepts_valid_path_with_hyphens_and_underscores(self):
        # This will fail at the credential parsing step (not at validation),
        # proving the path passed the sanitization check.
        with pytest.raises(Exception) as exc_info:
            _validate_gcp_automated_sync("my-project.billing_dataset.gcp_billing_export_v1", '{"type":"service_account"}')
        # Should NOT be the "invalid characters" error
        assert "invalid characters" not in str(exc_info.value)

    def test_rejects_unicode_escape_attempt(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_gcp_automated_sync("project.dataset.tàble", "{}")
        assert exc_info.value.status_code == 400
        assert "invalid characters" in exc_info.value.detail

    def test_rejects_newline_injection(self):
        with pytest.raises(HTTPException) as exc_info:
            _validate_gcp_automated_sync("project.dataset.table\n--", "{}")
        assert exc_info.value.status_code == 400
