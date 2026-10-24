import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from fastapi import APIRouter, Header, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel
from backend.services.supabase_client import supabase
from backend.services.auth_service import (
    hash_password,
    verify_password,
    create_token,
    decode_token,
    validate_password,
    validate_email,

)
from backend.services.user_store import (
    find_raw_by_email,
    find_by_id,
    create_user,
    touch_last_login,
    record_login,
    _to_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ---------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------

_attempts = defaultdict(list)
_attempts_lock = Lock()


def check_rate_limit(request: Request, limit: int = 15):
    ip = request.client.host if request.client else "unknown"
    now = time.time()

    with _attempts_lock:
        recent = [
            timestamp
            for timestamp in _attempts[ip]
            if now - timestamp < 900
        ]
        _attempts[ip] = recent

        if len(recent) >= limit:
            raise HTTPException(
                status_code=429,
                detail={"error": "Too many requests"},
            )

        _attempts[ip].append(now)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def error(status: int, message: str, field: str | None = None):
    detail = {"error": message}

    if field:
        detail["field"] = field

    raise HTTPException(status_code=status, detail=detail)


def valid_email(email: str) -> bool:
    return validate_email(email)


def record_login_safely(user_id: str):
    """Do not block authentication if login-history recording fails."""
    try:
        record_login(user_id)
    except Exception as exc:
        print(f"Login history recording failed: {exc}")


def response_user(user: dict) -> dict:
    """Return only fields that are safe to expose to the frontend."""
    return {
        "id": user["id"],
        "firstName": user.get("firstName", ""),
        "lastName": user.get("lastName", ""),
        "email": user["email"],
        "provider": user.get("provider", "email"),
        "createdAt": user.get("createdAt"),
        "lastLoginAt": user.get("lastLoginAt"),
    }


# ---------------------------------------------------------
# Request models
# ---------------------------------------------------------

class SignupRequest(BaseModel):
    firstName: str
    lastName: str = ""
    email: str
    password: str


class SigninRequest(BaseModel):
    email: str
    password: str


class GoogleRequest(BaseModel):
    credential: str


# ---------------------------------------------------------
# Signup
# POST /auth/signup
# ---------------------------------------------------------

@router.post("/signup", status_code=201)
def signup(body: SignupRequest, request: Request):
    check_rate_limit(request)

    first_name = body.firstName.strip()
    last_name = body.lastName.strip()
    email = body.email.strip().lower()

    if not first_name:
        error(400, "First name required", "firstName")

    if not valid_email(email):
        error(400, "Valid email required", "email")

    valid, message = validate_password(body.password)

    if not valid:
        error(400, message, "password")

    try:
        if find_raw_by_email(email):
            error(
                409,
                "An account with this email already exists",
                "email",
            )

        user = create_user(
            user_id=str(uuid.uuid4()),
            first_name=first_name,
            last_name=last_name,
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

    except Exception as exc:
        # Handle a duplicate email rejected by a database constraint.
        message = str(exc).lower()

        if (
            "23505" in message
            or "already exists" in message
            or "duplicate key" in message
        ):
            error(
                409,
                "An account with this email already exists",
                "email",
            )

        print(f"Signup error: {exc}")
        error(500, "Could not create account")


# ---------------------------------------------------------
# Signin
# POST /auth/signin
# ---------------------------------------------------------

@router.post("/signin")
def signin(body: SigninRequest, request: Request):
    check_rate_limit(request, limit=10)

    email = body.email.strip().lower()

    if not email or not body.password:
        error(400, "Email and password required")

    try:
        raw = find_raw_by_email(email)
        password_hash = raw.get("passwordHash") if raw else None

        if (
            not raw
            or not password_hash
            or not verify_password(body.password, password_hash)
        ):
            error(401, "Incorrect email or password")

        last_login = touch_last_login(raw["id"])
        record_login_safely(raw["id"])

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

    except Exception as exc:
        print(f"Signin error: {exc}")
        error(500, "Could not sign in")


# ---------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------

def bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        error(401, "Authentication required")

    token = authorization[7:].strip()

    if not token:
        error(401, "Authentication required")

    return token


# ---------------------------------------------------------
# Current user
# GET /auth/me
# ---------------------------------------------------------

@router.get("/me")
def me(authorization: str | None = Header(default=None)):
    token = bearer_token(authorization)

    try:
        payload = decode_token(token)

    except ValueError as exc:
        error(401, str(exc))

    user_id = payload.get("sub")

    if not user_id:
        error(401, "Invalid authentication token")

    try:
        user = find_by_id(user_id)

    except Exception as exc:
        print(f"Auth /me error: {exc}")
        error(500, "Could not fetch user")

    if not user:
        error(401, "User not found")

    return {"user": response_user(user)}


# ---------------------------------------------------------
# Logout
# POST /auth/logout
# ---------------------------------------------------------

@router.post("/logout")
def logout():
    # JWT logout is client-side unless token revocation is implemented.
    return {"message": "Logged out"}


# ---------------------------------------------------------
# Google authentication
# POST /auth/google
# ---------------------------------------------------------

@router.post("/google")
def google_login(body: GoogleRequest, request: Request):
    check_rate_limit(request, limit=10)

    if not body.credential:
        error(400, "Google credential required")

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
        # 1. Find an account linked to this Google identity.
        existing = (
            supabase.table("users")
            .select("*")
            .eq("google_sub", google_sub)
            .limit(1)
            .execute()
        )

        row = existing.data[0] if existing.data else None

        if row is None:
            # 2. Check whether the email belongs to an existing account.
            by_email = (
                supabase.table("users")
                .select("*")
                .eq("email", email)
                .limit(1)
                .execute()
            )

            email_row = by_email.data[0] if by_email.data else None

            if email_row:
                # Preserve the original account-linking policy.
                is_gmail = email.endswith("@gmail.com")
                hosted_domain = payload.get("hd")

                if not (is_gmail or hosted_domain):
                    error(
                        409,
                        (
                            "An account with this email already exists. "
                            "Sign in with your password first."
                        ),
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
                # 3. Create a new Google account.
                now = datetime.now(timezone.utc).isoformat()

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

                if not created.data:
                    error(500, "Could not create Google account")

                row = created.data[0]

        user = _to_user(row)

        last_login = touch_last_login(user["id"])
        record_login_safely(user["id"])
        user["lastLoginAt"] = last_login

        return {
            "token": create_token(user),
            "user": response_user(user),
            "message": "Signed in with Google",
        }

    except HTTPException:
        raise

    except Exception as exc:
        print(f"Google authentication error: {exc}")
        error(500, "Could not sign in with Google")
