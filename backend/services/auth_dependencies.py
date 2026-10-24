
import logging

from fastapi import Header, HTTPException

from backend.services.auth_service import decode_token
from backend.services.user_store import find_by_id


logger = logging.getLogger(__name__)


def get_current_user(
    authorization: str | None = Header(default=None),
):
    if (
        not authorization
        or not authorization.lower().startswith("bearer ")
    ):
        raise HTTPException(
            status_code=401,
            detail={"error": "Authentication required"},
        )

    token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid or expired token"},
        )

    try:
        payload = decode_token(token)

    except Exception:
        logger.warning("Token validation failed.")
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid or expired token"},
        ) from None

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid token"},
        )

    user_id = payload.get("sub")

    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid token"},
        )

    try:
        user = find_by_id(user_id)

    except Exception:
        logger.exception("Failed to verify authenticated user.")
        raise HTTPException(
            status_code=500,
            detail={"error": "Unable to verify user"},
        ) from None

    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "User not found"},
        )

    return user
