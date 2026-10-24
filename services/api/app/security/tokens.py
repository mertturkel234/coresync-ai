"""JWT access tokens (HS256, server-side secret)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import jwt

from app.core.config import Settings
from app.db.base import utcnow

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    pass


def create_access_token(settings: Settings, user_id: uuid.UUID) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    now = utcnow()
    ttl = timedelta(minutes=settings.jwt_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), int(ttl.total_seconds())


def decode_access_token(settings: Settings, token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],  # never accept the algorithm from the token header
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
        if payload.get("typ") != "access":
            raise InvalidTokenError("wrong token type")
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise InvalidTokenError("invalid token") from exc
