"""
Configuration settings for the CloudFinOps Python backend.
Loads environment variables and provides typed settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


DEFAULT_GEMINI_FLASH_MODEL = "gemini-3.7-flash"
DEFAULT_GEMINI_FAST_MODEL = DEFAULT_GEMINI_FLASH_MODEL


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App
    app_name: str = "CloudFinOps Backend"
    debug: bool = False
    
    # Clerk Authentication
    clerk_secret_key: str
    clerk_jwks_url: str = "https://api.clerk.dev/v1/jwks"
    
    # MongoDB
    mongodb_uri: str
    mongodb_db_name: str = "cloudfinops"
    
    # API Keys
    nvidia_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None  # Google Gemini for AI enrichment
    infracost_api_key: Optional[str] = None
    gcp_billing_catalog_api_key: Optional[str] = None
    gemini_verify_model: str = DEFAULT_GEMINI_FAST_MODEL
    gemini_propose_model: str = DEFAULT_GEMINI_FLASH_MODEL
    gemini_agent_model: str = DEFAULT_GEMINI_FLASH_MODEL
    gemini_fix_model: str = DEFAULT_GEMINI_FAST_MODEL
    gemini_bill_model: str = DEFAULT_GEMINI_FLASH_MODEL
    slack_signing_secret: Optional[str] = None

    # Raw bill archival (private Google Cloud Storage)
    gcs_bill_upload_bucket: Optional[str] = None
    gcs_bill_upload_prefix: str = "bill-uploads"
    gcs_bill_upload_credentials_json: Optional[str] = None

    # Encryption (for decrypting stored credentials)
    encryption_key: str
    
    # AI (NVIDIA)
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    
    # Redis (for ARQ background tasks)
    redis_url: str = "redis://localhost:6379"
    
    # CORS
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Expose common settings as module-level variables for convenience
# Wrapped in try/except to prevent import-time crash if env vars are missing
try:
    settings = get_settings()
    MONGODB_URI = settings.mongodb_uri
    MONGODB_DB_NAME = settings.mongodb_db_name
    NVIDIA_API_KEY = settings.nvidia_api_key
    GEMINI_API_KEY = settings.gemini_api_key
    GCP_BILLING_CATALOG_API_KEY = settings.gcp_billing_catalog_api_key
    GEMINI_VERIFY_MODEL = settings.gemini_verify_model
    GEMINI_PROPOSE_MODEL = settings.gemini_propose_model
    GEMINI_AGENT_MODEL = settings.gemini_agent_model
    GEMINI_FIX_MODEL = settings.gemini_fix_model
    GEMINI_BILL_MODEL = settings.gemini_bill_model
    GCS_BILL_UPLOAD_BUCKET = settings.gcs_bill_upload_bucket
    GCS_BILL_UPLOAD_PREFIX = settings.gcs_bill_upload_prefix
    GCS_BILL_UPLOAD_CREDENTIALS_JSON = settings.gcs_bill_upload_credentials_json
    ENCRYPTION_KEY = settings.encryption_key
except Exception as e:
    import logging
    _logger = logging.getLogger(__name__)
    _logger.error(
        "Failed to load settings from environment: %s. "
        "Ensure all required env vars are set (CLERK_SECRET_KEY, "
        "MONGODB_URI, ENCRYPTION_KEY).",
        e,
    )
    # Fail fast: set settings to None so first request raises a clear error
    settings = None
    MONGODB_URI = ""
    MONGODB_DB_NAME = "cloudfinops"
    NVIDIA_API_KEY = None
    GEMINI_API_KEY = None
    GCP_BILLING_CATALOG_API_KEY = None
    GEMINI_VERIFY_MODEL = DEFAULT_GEMINI_FAST_MODEL
    GEMINI_PROPOSE_MODEL = DEFAULT_GEMINI_FLASH_MODEL
    GEMINI_AGENT_MODEL = DEFAULT_GEMINI_FLASH_MODEL
    GEMINI_FIX_MODEL = DEFAULT_GEMINI_FAST_MODEL
    GEMINI_BILL_MODEL = DEFAULT_GEMINI_FLASH_MODEL
    GCS_BILL_UPLOAD_BUCKET = None
    GCS_BILL_UPLOAD_PREFIX = "bill-uploads"
    GCS_BILL_UPLOAD_CREDENTIALS_JSON = None
    ENCRYPTION_KEY = None  # Intentionally None — credential decryption will fail loudly
