
import os
import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv


load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password must not be empty.")

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError(
            "Password must not exceed 72 UTF-8 bytes."
        )

    return bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(rounds=10),
    ).decode("utf-8")


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """Verify a password against its bcrypt hash."""
    if not isinstance(password, str):
        return False

    if not isinstance(password_hash, str):
        return False

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_token(user: dict) -> str:
    """Create a signed JWT for an authenticated user."""
    if not JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET is missing from the environment."
        )

    if not isinstance(user, dict):
        raise ValueError("User must be a dictionary.")

    user_id = user.get("id")
    email = user.get("email")

    if user_id is None or not str(user_id).strip():
        raise ValueError("User ID is required to create a token.")

    if not isinstance(email, str) or not email.strip():
        raise ValueError("User email is required to create a token.")

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "email": email,
        "firstName": user.get("firstName", ""),
        "iat": now,
        "exp": now + timedelta(days=JWT_EXPIRY_DAYS),
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    """Verify a JWT signature and its expiration."""
    if not JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET is missing from the environment."
        )

    if not isinstance(token, str) or not token.strip():
        raise ValueError("Token is required.")

    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise ValueError(
            "Session expired — please sign in again."
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid token.") from exc


def validate_email(email: str) -> bool:
    """Perform basic email-format validation."""
    if not isinstance(email, str):
        return False

    return bool(
        re.fullmatch(
            r"[^\s@]+@[^\s@]+\.[^\s@]+",
            email.strip(),
        )
    )


def validate_password(password: str) -> tuple[bool, str]:
    """Check the minimum password requirements."""
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters."

    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one number."

    return True, ""
