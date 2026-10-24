
from datetime import datetime, timezone

from backend.services.supabase_client import supabase


def _to_user(row: dict) -> dict:
    """Convert a Supabase user row into the public user format."""
    return {
        "id": row["id"],
        "firstName": row.get("first_name") or "",
        "lastName": row.get("last_name") or "",
        "email": row["email"],
        "provider": row.get("provider") or "email",
        "createdAt": row.get("created_at"),
        "lastLoginAt": row.get("last_login_at"),
    }


def find_raw_by_email(email: str):
    """Find a user by email, including private authentication fields."""
    if not isinstance(email, str) or not email.strip():
        return None

    normalized_email = email.strip().lower()

    response = (
        supabase.table("users")
        .select("*")
        .eq("email", normalized_email)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    row = response.data[0]

    return {
        **_to_user(row),
        "passwordHash": row.get("password_hash"),
        "googleSub": row.get("google_sub"),
    }


def find_by_id(user_id: str):
    """Find a user by ID without returning private authentication fields."""
    if user_id is None or not str(user_id).strip():
        return None

    response = (
        supabase.table("users")
        .select("*")
        .eq("id", str(user_id))
        .limit(1)
        .execute()
    )

    return _to_user(response.data[0]) if response.data else None


def create_user(
    user_id: str,
    first_name: str,
    last_name: str,
    email: str,
    password_hash: str,
    provider: str = "email",
):
    """Create a user and return the public user representation."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("User ID is required.")

    if not isinstance(email, str) or not email.strip():
        raise ValueError("Email is required.")

    if not isinstance(password_hash, str) or not password_hash.strip():
        raise ValueError("Password hash is required.")

    if not isinstance(first_name, str) or not first_name.strip():
        raise ValueError("First name is required.")

    if not isinstance(last_name, str) or not last_name.strip():
        raise ValueError("Last name is required.")

    if not isinstance(provider, str) or not provider.strip():
        raise ValueError("Provider is required.")

    normalized_email = email.strip().lower()
    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("users")
        .insert({
            "id": user_id.strip(),
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "email": normalized_email,
            "password_hash": password_hash,
            "provider": provider.strip(),
            "created_at": now,
        })
        .execute()
    )

    if not response.data:
        raise RuntimeError("Supabase did not return the created user.")

    return _to_user(response.data[0])


def touch_last_login(user_id: str):
    """Update the user's last-login timestamp."""
    if user_id is None or not str(user_id).strip():
        raise ValueError("User ID is required.")

    now = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("users")
        .update({"last_login_at": now})
        .eq("id", str(user_id))
        .execute()
    )

    if not response.data:
        raise RuntimeError("Unable to update the user's last-login timestamp.")

    return now


def record_login(user_id: str):
    """Record login history when possible; this is an optional feature."""
    if user_id is None or not str(user_id).strip():
        return

    try:
        supabase.table("login_history").insert({
            "user_id": str(user_id)
        }).execute()
    except Exception:
        # Login history is optional; authentication should still work.
        pass
