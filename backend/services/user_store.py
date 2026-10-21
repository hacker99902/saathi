from datetime import datetime, timezone

from backend.services.supabase_client import supabase


def _to_user(row: dict) -> dict:
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
    response = (
        supabase.table("users")
        .select("*")
        .ilike("email", email.strip())
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
    response = (
        supabase.table("users")
        .select("*")
        .eq("id", user_id)
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
    now = datetime.now(timezone.utc).isoformat()

    response = supabase.table("users").insert({
        "id": user_id,
        "first_name": first_name.strip(),
        "last_name": last_name.strip(),
        "email": email.strip().lower(),
        "password_hash": password_hash,
        "provider": provider,
        "created_at": now,
    }).execute()

    if not response.data:
        raise RuntimeError("Supabase did not return the created user.")

    return _to_user(response.data[0])


def touch_last_login(user_id: str):
    now = datetime.now(timezone.utc).isoformat()

    supabase.table("users").update({
        "last_login_at": now
    }).eq("id", user_id).execute()

    return now


def record_login(user_id: str):
    try:
        supabase.table("login_history").insert({
            "user_id": user_id
        }).execute()
    except Exception:
        # Login history is optional; authentication should still work.
        pass
