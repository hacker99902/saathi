import re
import time
import uuid
from collections import defaultdict
from threading import Lock
import os
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from backend.services.supabase_client import supabase
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr

from backend.services.auth_service import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
    validate_password,
)
from backend.services.user_store import (
    find_raw_by_email,
    find_by_id,
    create_user,
    touch_last_login,
    record_login,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

_attempts = defaultdict(list)
_attempts_lock = Lock()


def check_rate_limit(request: Request, limit: int = 15):
    ip = request.client.host if request.client else "unknown"
    now = time.time()

    with _attempts_lock:
        recent = [t for t in _attempts[ip] if now - t < 900]
        _attempts[ip] = recent

        if len(recent) >= limit:
            raise HTTPException(
                status_code=429,
                detail={"error": "Too many requests"},
            )

        _attempts[ip].append(now)


def error(status: int, message: str, field: str | None = None):
    detail = {"error": message}
    if field:
        detail["field"] = field
    raise HTTPException(status_code=status, detail=detail)


class SignupRequest(BaseModel):
    firstName: str
    lastName: str = ""
    email: str
    password: str


class SigninRequest(BaseModel):
    email: str
    password: str


def response_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "firstName": user.get("firstName", ""),
        "lastName": user.get("lastName", ""),
        "email": user["email"],
        "provider": user.get("provider", "email"),
        "createdAt": user.get("createdAt"),
        "lastLoginAt": user.get("lastLoginAt"),
    }


@router.post("/signup", status_code=201)
def signup(body: SignupRequest, request: Request):
    check_rate_limit(request)

    first_name = body.firstName.strip()
    email = body.email.strip().lower()

    if not first_name:
        error(400, "First name required", "firstName")

    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        error(400, "Valid email required", "email")

    valid, message = validate_password(body.password)
    if not valid:
        error(400, message, "password")

    try:
        if find_raw_by_email(email):
            error(409, "An account with this email already exists", "email")

        user = create_user(
            user_id=str(uuid.uuid4()),
            first_name=first_name,
            last_name=body.lastName or "",
            email=email,
            password_hash=hash_password(body.password),
            provider="email",
        )

        token = create_token(user)

        return {
            "token": token,
            "user": response_user(user),
            "message": "Account created",
        }

    except HTTPException:
        raise
    except Exception:
        error(500, "Could not create account")


@router.post("/signin")
def signin(body: SigninRequest, request: Request):
    check_rate_limit(request, limit=10)

    email = body.email.strip().lower()

    if not email or not body.password:
        error(400, "Email and password required")

    try:
        raw = find_raw_by_email(email)
        password_hash = raw.get("passwordHash") if raw else None

        if not raw or not password_hash or not verify_password(
            body.password, password_hash
        ):
            error(401, "Incorrect email or password")

        last_login = touch_last_login(raw["id"])
        record_login(raw["id"])

        user = {
            **raw,
            "lastLoginAt": last_login,
        }
        token = create_token(user)

        return {
            "token": token,
            "user": response_user(user),
            "message": "Signed in",
        }

    except HTTPException:
        raise
    except Exception:
        error(500, "Could not sign in")


def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        error(401, "Authentication required")

    return authorization[7:].strip()


@router.get("/me")
def me(authorization: str | None = Header(default=None)):
    token = bearer_token(authorization)

    try:
        payload = decode_token(token)
    except ValueError as exc:
        error(401, str(exc))

    user = find_by_id(payload["sub"])
    if not user:
        error(401, "User not found")

    return {"user": response_user(user)}


@router.post("/logout")
def logout():
    return {"message": "Logged out"}

class GoogleRequest(BaseModel):
    credential: str


@router.post("/google")
def google_login(body: GoogleRequest, request: Request):
    check_rate_limit(request, limit=10)

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        error(500, "Google authentication is not configured")

    try:
        payload = id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            client_id,
        )
    except Exception:
        error(401, "Invalid Google credential")

    google_sub = payload.get("sub")
    email = (payload.get("email") or "").strip().lower()

    if not google_sub or not email:
        error(400, "Google account information is incomplete")

    if not payload.get("email_verified"):
        error(401, "Google email is not verified")

    first_name = (
        payload.get("given_name")
        or payload.get("name", "").split(" ")[0]
        or "Google"
    )
    last_name = payload.get("family_name") or ""

    try:
        existing = (
            supabase.table("users")
            .select("*")
            .eq("google_sub", google_sub)
            .limit(1)
            .execute()
        )

        row = existing.data[0] if existing.data else None

        if row is None:
            by_email = (
                supabase.table("users")
                .select("*")
                .ilike("email", email)
                .limit(1)
                .execute()
            )
            email_row = by_email.data[0] if by_email.data else None

            if email_row:
                # Link only when the existing account's email is eligible
                # under the original application's Google-linking policy.
                hosted_domain = payload.get("hd")
                is_gmail = email.endswith("@gmail.com")
                if not (is_gmail or hosted_domain):
                    error(
                        409,
                        "An account with this email already exists. Sign in with your password first.",
                    )

                update = {
                    "google_sub": google_sub,
                    "provider": email_row.get("provider") or "google",
                }
                supabase.table("users").update(update).eq(
                    "id", email_row["id"]
                ).execute()
                row = {**email_row, **update}
            else:
                now = __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat()

                created = (
                    supabase.table("users")
                    .insert({
                        "id": str(uuid.uuid4()),
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "provider": "google",
                        "google_sub": google_sub,
                        "created_at": now,
                    })
                    .execute()
                )
                row = created.data[0]

        from backend.services.user_store import _to_user, touch_last_login, record_login

        user = _to_user(row)
        user["lastLoginAt"] = touch_last_login(user["id"])
        record_login(user["id"])

        return {
            "token": create_token(user),
            "user": response_user(user),
            "message": "Signed in with Google",
        }

    except HTTPException:
        raise
    except Exception:
        error(500, "Could not sign in with Google")