import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes.")

    return bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(rounds=10)
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_token(user: dict) -> str:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is missing from the environment.")

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "firstName": user.get("firstName", ""),
        "iat": now,
        "exp": now + timedelta(days=JWT_EXPIRY_DAYS),
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is missing from the environment.")

    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError as exc:
        raise ValueError(
            "Session expired — please sign in again"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid token") from exc


def validate_email(email: str) -> bool:
    import re

    return bool(
        re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email or "")
    )


def validate_password(password: str) -> tuple[bool, str]:
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters"

    if not any(char.isdigit() for char in password):
        return False, "Password must contain at least one number"

    return True, ""
