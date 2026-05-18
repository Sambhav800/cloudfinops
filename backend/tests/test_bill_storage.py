from types import SimpleNamespace
from unittest.mock import patch

import pytest
from google.auth import exceptions as google_auth_exceptions

from app.core.bill_storage import RawBillStorageError, _refresh_access_token


class _BrokenCredentials:
    def refresh(self, request):
        raise google_auth_exceptions.RefreshError(
            "invalid_grant: Bad Request",
            {"error": "invalid_grant", "error_description": "Bad Request"},
        )


def test_refresh_access_token_uses_gcloud_fallback_when_adc_refresh_is_invalid():
    with patch("app.core.bill_storage._build_scoped_credentials", return_value=_BrokenCredentials()):
        with patch("app.core.bill_storage.shutil.which", return_value="/usr/bin/gcloud"):
            with patch(
                "app.core.bill_storage.subprocess.run",
                return_value=SimpleNamespace(stdout="ya29.test-token\n"),
            ) as mocked_run:
                token = _refresh_access_token("https://www.googleapis.com/auth/devstorage.read_write")

    assert token == "ya29.test-token"
    mocked_run.assert_called_once()


def test_refresh_access_token_raises_when_adc_and_gcloud_fallback_both_fail():
    with patch("app.core.bill_storage._build_scoped_credentials", return_value=_BrokenCredentials()):
        with patch("app.core.bill_storage.shutil.which", return_value=None):
            with pytest.raises(RawBillStorageError):
                _refresh_access_token("https://www.googleapis.com/auth/devstorage.read_write")
