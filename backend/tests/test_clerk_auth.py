from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request
import pytest

from app.auth.clerk import ClerkUser, get_current_user
from app.config import Settings


def _make_request(
    headers: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> Request:
    encoded_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test-auth",
        "headers": encoded_headers,
        "query_string": b"",
        "client": (client_host, 12345),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
        "http_version": "1.1",
    }
    return Request(scope)


def _settings(frontend_url: str) -> Settings:
    return Settings(
        clerk_secret_key="sk_test_clerk",
        mongodb_uri="mongodb://localhost:27017/cloudfinops",
        encryption_key="test-encryption-key",
        frontend_url=frontend_url,
    )


@pytest.mark.asyncio
async def test_get_current_user_rejects_user_id_header_even_on_loopback_dev() -> None:
    request = _make_request(headers={"x-cloudfinops-user-id": "user-local"})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=request,
            credentials=None,
            settings=_settings("http://localhost:3000"),
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Missing authentication credentials"


@pytest.mark.asyncio
async def test_get_current_user_accepts_valid_bearer_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_verify(token: str, settings: Settings) -> ClerkUser:
        assert token == "token-123"
        assert settings.frontend_url == "http://localhost:3000"
        return ClerkUser(id="user-token", email="user@example.com")

    monkeypatch.setattr("app.auth.clerk.verify_clerk_token", fake_verify)

    request = _make_request()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token-123")

    user = await get_current_user(
        request=request,
        credentials=credentials,
        settings=_settings("http://localhost:3000"),
    )

    assert user.id == "user-token"
    assert user.email == "user@example.com"


@pytest.mark.asyncio
async def test_get_current_user_rejects_missing_credentials() -> None:
    request = _make_request()

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(
            request=request,
            credentials=None,
            settings=_settings("http://localhost:3000"),
        )

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Missing authentication credentials"
