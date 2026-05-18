from typing import Any, Optional


def resolve_user_email(user: Any) -> Optional[str]:
    email = getattr(user, "email", None)
    if isinstance(email, str) and email.strip():
        return email.strip()

    email_addresses = getattr(user, "email_addresses", None)
    if isinstance(email_addresses, list) and email_addresses:
        first = email_addresses[0]
        if isinstance(first, dict):
            candidate = first.get("email_address")
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        else:
            candidate = getattr(first, "email_address", None)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

    return None


def resolve_user_full_name(user: Any) -> Optional[str]:
    first_name = getattr(user, "first_name", None)
    last_name = getattr(user, "last_name", None)
    if isinstance(first_name, str):
        first_name = first_name.strip()
    else:
        first_name = ""
    if isinstance(last_name, str):
        last_name = last_name.strip()
    else:
        last_name = ""

    full_name = " ".join(part for part in [first_name, last_name] if part).strip()
    return full_name or None
