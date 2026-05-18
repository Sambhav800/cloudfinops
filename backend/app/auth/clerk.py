"""
Clerk JWT Authentication Middleware for FastAPI.
Verifies JWT tokens issued by Clerk and extracts user information.
"""

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from pydantic import BaseModel
from typing import Any, Optional
import logging
import time

from ..config import get_settings, Settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class ClerkUser(BaseModel):
    """Authenticated user from Clerk JWT."""
    id: str  # Clerk user ID (sub claim)
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class ClerkJWKS:
    """Cache and manage Clerk JWKS (JSON Web Key Set)."""
    
    def __init__(self):
        self.keys: dict = {}
        self.last_fetch: float = 0
        self.cache_duration: int = 3600  # 1 hour
    
    async def get_key(self, kid: str, settings: Settings) -> Optional[dict]:
        """Get public key by key ID, fetching JWKS if needed."""
        # Refresh cache if expired
        if time.time() - self.last_fetch > self.cache_duration:
            await self._fetch_jwks(settings)
        
        return self.keys.get(kid)
    
    async def _fetch_jwks(self, settings: Settings):
        """Fetch JWKS from Clerk."""
        try:
            async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0")) as client:
                # Clerk JWKS endpoint
                jwks_url = f"https://api.clerk.dev/v1/jwks"
                headers = {"Authorization": f"Bearer {settings.clerk_secret_key}"}
                
                response = await client.get(jwks_url, headers=headers)
                response.raise_for_status()
                
                jwks = response.json()
                self.keys = {key["kid"]: key for key in jwks.get("keys", [])}
                self.last_fetch = time.time()
        except Exception as e:
            logger.error("Failed to fetch Clerk JWKS: %s", e)
            # Keep existing keys if fetch fails


# Global JWKS cache
_jwks_cache = ClerkJWKS()


def _claim_string(payload: dict[str, Any], keys: list[str]) -> Optional[str]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_clerk_email(payload: dict[str, Any]) -> Optional[str]:
    direct = _claim_string(payload, ["email", "email_address"])
    if direct:
        return direct

    email_addresses = payload.get("email_addresses")
    if isinstance(email_addresses, list):
        for item in email_addresses:
            if isinstance(item, dict):
                candidate = item.get("email_address")
            else:
                candidate = getattr(item, "email_address", None)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return None


def _extract_clerk_first_name(payload: dict[str, Any]) -> Optional[str]:
    return _claim_string(payload, ["first_name", "given_name"])


def _extract_clerk_last_name(payload: dict[str, Any]) -> Optional[str]:
    return _claim_string(payload, ["last_name", "family_name"])


async def verify_clerk_token(token: str, settings: Settings) -> ClerkUser:
    """Verify Clerk JWT and extract user information."""
    try:
        # Decode header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing key ID"
            )
        
        # Get public key
        public_key = await _jwks_cache.get_key(kid, settings)
        
        if not public_key:
            # Force refresh and try again
            await _jwks_cache._fetch_jwks(settings)
            public_key = await _jwks_cache.get_key(kid, settings)
        
        if not public_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: unknown key"
            )
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False}  # Clerk doesn't always set audience
        )
        
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject"
            )

        # Extract user info
        return ClerkUser(
            id=user_id.strip(),
            email=_extract_clerk_email(payload),
            first_name=_extract_clerk_first_name(payload),
            last_name=_extract_clerk_last_name(payload),
        )
        
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    settings: Settings = Depends(get_settings)
) -> ClerkUser:
    """
    FastAPI dependency to get the current authenticated user.
    
    Usage:
        @app.get("/protected")
        async def protected_route(user: ClerkUser = Depends(get_current_user)):
            return {"user_id": user.id}
    """
    if credentials and credentials.credentials:
        return await verify_clerk_token(credentials.credentials, settings)

    dev_user_id = request.headers.get("x-cloudfinops-user-id")
    if dev_user_id:
        logger.warning(
            "Rejected deprecated x-cloudfinops-user-id header from %s",
            request.client.host if request.client else "unknown",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials"
    )
