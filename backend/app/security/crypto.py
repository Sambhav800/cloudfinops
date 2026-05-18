"""
Security utilities for the CloudFinOps backend.
Handles encryption and decryption of stored cloud credentials.
"""

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os

from ..config import get_settings


def encrypt(plaintext: str) -> tuple[str, str]:
    """
    Encrypt a plaintext value using the same AES-256-GCM contract as the frontend.
    Returns (encrypted_data, iv), where encrypted_data is `ciphertext:auth_tag`.
    """
    settings = get_settings()
    iv_bytes = os.urandom(12)
    key_bytes = bytes.fromhex(settings.encryption_key)

    cipher = Cipher(
        algorithms.AES(key_bytes),
        modes.GCM(iv_bytes),
        backend=default_backend(),
    )

    encryptor = cipher.encryptor()
    encrypted = encryptor.update(plaintext.encode("utf-8")) + encryptor.finalize()

    encrypted_hex = encrypted.hex()
    auth_tag_hex = encryptor.tag.hex()
    return f"{encrypted_hex}:{auth_tag_hex}", iv_bytes.hex()


def decrypt(encrypted_data: str, iv: str) -> str:
    """
    Decrypt a value that was encrypted by the frontend.
    Matches the encryption logic in src/lib/security/crypto.ts
    
    Frontend format: 'encrypted:authTag' (both in hex)
    IV: separate hex string
    """
    settings = get_settings()
    
    # Split encrypted data and auth tag (frontend uses colon separator)
    parts = encrypted_data.split(':')
    if len(parts) != 2:
        raise ValueError(f"Invalid encrypted data format, expected 'encrypted:authTag', got: {encrypted_data[:50]}...")
    
    encrypted_hex, auth_tag_hex = parts
    
    # Convert from hex to bytes
    encrypted_bytes = bytes.fromhex(encrypted_hex)
    auth_tag_bytes = bytes.fromhex(auth_tag_hex)
    iv_bytes = bytes.fromhex(iv)
    key_bytes = bytes.fromhex(settings.encryption_key)
    
    # Create cipher in GCM mode
    cipher = Cipher(
        algorithms.AES(key_bytes),
        modes.GCM(iv_bytes, auth_tag_bytes),  # Pass tag during initialization
        backend=default_backend()
    )
    
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(encrypted_bytes) + decryptor.finalize()
    
    return decrypted.decode("utf-8")


def parse_encrypted_field(field: str) -> tuple[str, str]:
    """
    Parse an encrypted field stored as 'encrypted::iv' format.
    Returns (encrypted_data, iv)
    """
    parts = field.split("::")
    if len(parts) != 2:
        raise ValueError(f"Invalid encrypted field format: {field}")
    return parts[0], parts[1]


def decrypt_integration_credentials(integration: dict) -> dict:
    """
    Decrypt all credentials from a cloud integration record.
    Returns a dict with the decrypted values.
    """
    credentials = {}
    
    # AWS Keys
    if integration.get("encrypted_access_key_id"):
        enc, iv = parse_encrypted_field(integration["encrypted_access_key_id"])
        credentials["access_key_id"] = decrypt(enc, iv)
    
    if integration.get("encrypted_secret_access_key"):
        enc, iv = parse_encrypted_field(integration["encrypted_secret_access_key"])
        credentials["secret_access_key"] = decrypt(enc, iv)
    
    # AWS Role
    if integration.get("encrypted_role_arn"):
        enc, iv = parse_encrypted_field(integration["encrypted_role_arn"])
        credentials["role_arn"] = decrypt(enc, iv)
    
    if integration.get("encrypted_external_id"):
        enc, iv = parse_encrypted_field(integration["encrypted_external_id"])
        credentials["external_id"] = decrypt(enc, iv)
    
    # Azure
    if integration.get("encrypted_tenant_id"):
        enc, iv = parse_encrypted_field(integration["encrypted_tenant_id"])
        credentials["tenant_id"] = decrypt(enc, iv)
    
    if integration.get("encrypted_client_id"):
        enc, iv = parse_encrypted_field(integration["encrypted_client_id"])
        credentials["client_id"] = decrypt(enc, iv)
    
    if integration.get("encrypted_client_secret"):
        enc, iv = parse_encrypted_field(integration["encrypted_client_secret"])
        credentials["client_secret"] = decrypt(enc, iv)
    
    if integration.get("encrypted_subscription_id"):
        enc, iv = parse_encrypted_field(integration["encrypted_subscription_id"])
        credentials["subscription_id"] = decrypt(enc, iv)
    
    # GCP
    if integration.get("encrypted_project_id"):
        enc, iv = parse_encrypted_field(integration["encrypted_project_id"])
        credentials["project_id"] = decrypt(enc, iv)
    
    if integration.get("encrypted_service_account_email"):
        enc, iv = parse_encrypted_field(integration["encrypted_service_account_email"])
        credentials["service_account_email"] = decrypt(enc, iv)
    
    if integration.get("encrypted_private_key"):
        enc, iv = parse_encrypted_field(integration["encrypted_private_key"])
        credentials["private_key"] = decrypt(enc, iv)
    
    return credentials
