from app.api.routes import UserSyncRequest, _build_synced_user_record
from app.auth import ClerkUser


def test_build_synced_user_record_preserves_existing_profile_when_new_values_missing():
    record = _build_synced_user_record(
        existing_user={
            "id": "user-1",
            "email": "existing@example.com",
            "email_lower": "existing@example.com",
            "first_name": "Existing",
            "last_name": "User",
            "full_name": "Existing User",
            "avatar_url": "https://cdn.example.com/existing.png",
        },
        payload=UserSyncRequest(),
        auth_user=ClerkUser(id="user-1"),
        now_iso="2026-03-22T12:00:00+00:00",
    )

    assert record["email"] == "existing@example.com"
    assert record["email_lower"] == "existing@example.com"
    assert record["first_name"] == "Existing"
    assert record["last_name"] == "User"
    assert record["full_name"] == "Existing User"
    assert record["avatar_url"] == "https://cdn.example.com/existing.png"
    assert record["last_login"] == "2026-03-22T12:00:00+00:00"


def test_build_synced_user_record_prefers_payload_then_auth_fields_and_sets_email_lower():
    record = _build_synced_user_record(
        existing_user={"id": "user-1"},
        payload=UserSyncRequest(
            email="NishantJ0803@gmail.com",
            first_name="Nishant",
            last_name="Jain",
            avatar_url="https://cdn.example.com/avatar.png",
        ),
        auth_user=ClerkUser(
            id="user-1",
            email="fallback@example.com",
            first_name="Ignored",
            last_name="User",
        ),
        now_iso="2026-03-22T12:00:00+00:00",
    )

    assert record["email"] == "NishantJ0803@gmail.com"
    assert record["email_lower"] == "nishantj0803@gmail.com"
    assert record["first_name"] == "Nishant"
    assert record["last_name"] == "Jain"
    assert record["full_name"] == "Nishant Jain"
    assert record["avatar_url"] == "https://cdn.example.com/avatar.png"
