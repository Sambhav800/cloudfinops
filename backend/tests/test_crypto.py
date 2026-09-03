"""
Tests for backend/app/security/crypto.py — AES-256-GCM encryption/decryption.

Covers:
- Encrypt/decrypt roundtrip for various payloads
- IV uniqueness across encrypt calls
- Tampered ciphertext / auth-tag detection
- Invalid encrypted-data format handling
- parse_encrypted_field utility
- decrypt_integration_credentials per-field decryption
"""

import os
import pytest

# Set env vars BEFORE any app imports so get_settings() picks them up.
os.environ.setdefault("ENCRYPTION_KEY", "ac1d601fc216a6007afcdc7475e7fdb9ba89ee11c208fd8e3a9b9970ec3ad171")
os.environ.setdefault("CLERK_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")

# Clear the lru_cache so settings are re-loaded with our env vars.
from app.config import get_settings
get_settings.cache_clear()

from app.security.crypto import (
    decrypt,
    decrypt_integration_credentials,
    encrypt,
    parse_encrypted_field,
)


# ---------------------------------------------------------------------------
# Encrypt / decrypt roundtrip
# ---------------------------------------------------------------------------

class TestEncryptDecryptRoundtrip:
    """Encrypt then decrypt must return original plaintext."""

    def test_simple_string(self):
        enc_data, iv = encrypt("hello world")
        assert decrypt(enc_data, iv) == "hello world"

    def test_empty_string(self):
        enc_data, iv = encrypt("")
        assert decrypt(enc_data, iv) == ""

    def test_unicode(self):
        text = "prix: 42€ — élève"
        enc_data, iv = encrypt(text)
        assert decrypt(enc_data, iv) == text

    def test_long_string(self):
        text = "A" * 10_000
        enc_data, iv = encrypt(text)
        assert decrypt(enc_data, iv) == text

    def test_json_like_payload(self):
        text = '{"access_key": "AKIA1234", "secret": "s3cr3t"}'
        enc_data, iv = encrypt(text)
        assert decrypt(enc_data, iv) == text

    def test_multiline_string(self):
        text = "line1\nline2\nline3"
        enc_data, iv = encrypt(text)
        assert decrypt(enc_data, iv) == text

    def test_special_characters(self):
        text = "p@$$w0rd!#%^&*()_+-=[]{}|;':\",./<>?"
        enc_data, iv = encrypt(text)
        assert decrypt(enc_data, iv) == text


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------

class TestEncryptOutputFormat:
    """Verify the 'ciphertext:auth_tag' / hex IV format."""

    def test_encrypted_data_has_colon_separator(self):
        enc_data, iv = encrypt("test")
        parts = enc_data.split(":")
        assert len(parts) == 2, "encrypted_data should be 'ciphertext:auth_tag'"

    def test_iv_is_24_char_hex(self):
        """GCM uses a 12-byte IV => 24 hex characters."""
        _, iv = encrypt("test")
        assert len(iv) == 24
        int(iv, 16)  # must be valid hex

    def test_auth_tag_is_32_char_hex(self):
        """GCM auth tag is 16 bytes => 32 hex characters."""
        enc_data, _ = encrypt("test")
        _, tag_hex = enc_data.split(":")
        assert len(tag_hex) == 32
        int(tag_hex, 16)


# ---------------------------------------------------------------------------
# IV uniqueness (randomness)
# ---------------------------------------------------------------------------

class TestIVUniqueness:
    """Each encrypt call must produce a different IV."""

    def test_ivs_differ_across_calls(self):
        ivs = {encrypt("same plaintext")[1] for _ in range(20)}
        assert len(ivs) == 20, "IVs must be unique across encrypt calls"

    def test_ciphertexts_differ_for_same_plaintext(self):
        results = [encrypt("same plaintext")[0] for _ in range(10)]
        assert len(set(results)) == 10, "Ciphertexts must differ even for identical plaintext"


# ---------------------------------------------------------------------------
# Tampered ciphertext / tag detection
# ---------------------------------------------------------------------------

class TestTamperedCiphertext:
    """GCM must reject any modification of ciphertext or auth tag."""

    def test_flipped_bit_in_ciphertext_raises(self):
        enc_data, iv = encrypt("sensitive data")
        ct_hex, tag_hex = enc_data.split(":")
        # Flip the first hex digit
        flipped = ("0" if ct_hex[0] != "0" else "1") + ct_hex[1:]
        tampered = f"{flipped}:{tag_hex}"
        with pytest.raises(Exception):
            decrypt(tampered, iv)

    def test_flipped_bit_in_auth_tag_raises(self):
        enc_data, iv = encrypt("sensitive data")
        ct_hex, tag_hex = enc_data.split(":")
        flipped_tag = ("0" if tag_hex[0] != "0" else "1") + tag_hex[1:]
        tampered = f"{ct_hex}:{flipped_tag}"
        with pytest.raises(Exception):
            decrypt(tampered, iv)

    def test_wrong_iv_raises(self):
        enc_data, iv = encrypt("sensitive data")
        # Use a completely different IV
        wrong_iv = "00" * 12
        if wrong_iv == iv:
            wrong_iv = "ff" * 12
        with pytest.raises(Exception):
            decrypt(enc_data, wrong_iv)

    def test_truncated_ciphertext_raises(self):
        enc_data, iv = encrypt("sensitive data")
        ct_hex, tag_hex = enc_data.split(":")
        truncated = f"{ct_hex[:4]}:{tag_hex}"
        with pytest.raises(Exception):
            decrypt(truncated, iv)


# ---------------------------------------------------------------------------
# Invalid format handling
# ---------------------------------------------------------------------------

class TestInvalidFormat:
    """decrypt and parse_encrypted_field must reject bad formats."""

    def test_decrypt_rejects_no_colon(self):
        _, iv = encrypt("x")
        with pytest.raises(ValueError, match="Invalid encrypted data format"):
            decrypt("no_colon_here", iv)

    def test_decrypt_rejects_multiple_colons(self):
        _, iv = encrypt("x")
        with pytest.raises(ValueError, match="Invalid encrypted data format"):
            decrypt("a:b:c", iv)

    def test_decrypt_rejects_invalid_hex(self):
        _, iv = encrypt("x")
        with pytest.raises(ValueError):
            decrypt("zzzz:yyyy", iv)

    def test_parse_encrypted_field_rejects_no_double_colon(self):
        with pytest.raises(ValueError, match="Invalid encrypted field format"):
            parse_encrypted_field("missing-double-colon")

    def test_parse_encrypted_field_splits_correctly(self):
        enc, iv = parse_encrypted_field("abc:def::aabbcc")
        assert enc == "abc:def"
        assert iv == "aabbcc"


# ---------------------------------------------------------------------------
# decrypt_integration_credentials
# ---------------------------------------------------------------------------

class TestDecryptIntegrationCredentials:
    """Per-field decryption of stored cloud integration records."""

    def _make_encrypted_field(self, plaintext: str) -> str:
        """Encrypt a value and return it in the 'encrypted::iv' storage format."""
        enc_data, iv = encrypt(plaintext)
        return f"{enc_data}::{iv}"

    def test_aws_credentials(self):
        integration = {
            "encrypted_access_key_id": self._make_encrypted_field("AKIAIOSFODNN7EXAMPLE"),
            "encrypted_secret_access_key": self._make_encrypted_field("wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),
        }
        creds = decrypt_integration_credentials(integration)
        assert creds["access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
        assert creds["secret_access_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

    def test_aws_role_credentials(self):
        integration = {
            "encrypted_role_arn": self._make_encrypted_field("arn:aws:iam::123456789012:role/MyRole"),
            "encrypted_external_id": self._make_encrypted_field("ext-id-abc"),
        }
        creds = decrypt_integration_credentials(integration)
        assert creds["role_arn"] == "arn:aws:iam::123456789012:role/MyRole"
        assert creds["external_id"] == "ext-id-abc"

    def test_azure_credentials(self):
        integration = {
            "encrypted_tenant_id": self._make_encrypted_field("tenant-123"),
            "encrypted_client_id": self._make_encrypted_field("client-456"),
            "encrypted_client_secret": self._make_encrypted_field("secret-789"),
            "encrypted_subscription_id": self._make_encrypted_field("sub-012"),
        }
        creds = decrypt_integration_credentials(integration)
        assert creds["tenant_id"] == "tenant-123"
        assert creds["client_id"] == "client-456"
        assert creds["client_secret"] == "secret-789"
        assert creds["subscription_id"] == "sub-012"

    def test_gcp_credentials(self):
        integration = {
            "encrypted_project_id": self._make_encrypted_field("my-gcp-project"),
            "encrypted_service_account_email": self._make_encrypted_field("sa@project.iam.gserviceaccount.com"),
            "encrypted_private_key": self._make_encrypted_field("-----BEGIN PRIVATE KEY-----\nMIIE..."),
        }
        creds = decrypt_integration_credentials(integration)
        assert creds["project_id"] == "my-gcp-project"
        assert creds["service_account_email"] == "sa@project.iam.gserviceaccount.com"
        assert creds["private_key"] == "-----BEGIN PRIVATE KEY-----\nMIIE..."

    def test_empty_integration_returns_empty_dict(self):
        assert decrypt_integration_credentials({}) == {}

    def test_missing_fields_are_skipped(self):
        integration = {
            "encrypted_access_key_id": self._make_encrypted_field("AKIA"),
            # no secret_access_key at all
        }
        creds = decrypt_integration_credentials(integration)
        assert creds == {"access_key_id": "AKIA"}
        assert "secret_access_key" not in creds

    def test_mixed_provider_fields(self):
        """An integration with fields from multiple providers still decrypts all."""
        integration = {
            "encrypted_access_key_id": self._make_encrypted_field("aws-key"),
            "encrypted_tenant_id": self._make_encrypted_field("azure-tenant"),
            "encrypted_project_id": self._make_encrypted_field("gcp-proj"),
        }
        creds = decrypt_integration_credentials(integration)
        assert len(creds) == 3
        assert creds["access_key_id"] == "aws-key"
        assert creds["tenant_id"] == "azure-tenant"
        assert creds["project_id"] == "gcp-proj"
