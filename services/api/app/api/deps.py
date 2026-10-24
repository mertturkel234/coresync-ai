"""Shared FastAPI dependencies: request context, authentication, rate limiting."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AuthenticationError, RateLimitedError, get_request_id
from app.db.session import get_db
from app.models import User
from app.repositories import identity as identity_repo
from app.security.ratelimit import RateLimiter
from app.security.tokens import InvalidTokenError, decode_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    client_ip: str | None


def get_ctx(request: Request) -> RequestContext:
    # X-Forwarded-For is deliberately not trusted here; configure a trusted proxy layer before
    # relying on per-IP limits behind a reverse proxy (see docs/SECURITY.md).
    ip = request.client.host if request.client else None
    return RequestContext(request_id=get_request_id(request), client_ip=ip)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthenticationError()
    try:
        user_id = decode_access_token(settings, creds.credentials)
    except InvalidTokenError:
        raise AuthenticationError("Invalid or expired token.") from None
    user = identity_repo.get_user(db, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid or expired token.")
    return user


def enforce_rate_limit(limiter: RateLimiter, settings: Settings, key: str, limit: int) -> None:
    result = limiter.hit(key, limit, settings.rate_limit_window_seconds)
    if not result.allowed:
        raise RateLimitedError(retry_after=max(result.retry_after, 1))


def limit_by_ip(scope: str, limit_of: Callable[[Settings], int]) -> Callable[..., None]:
    def dependency(
        ctx: RequestContext = Depends(get_ctx),
        limiter: RateLimiter = Depends(get_limiter),
        settings: Settings = Depends(get_settings),
    ) -> None:
        enforce_rate_limit(limiter, settings, f"{scope}:ip:{ctx.client_ip}", limit_of(settings))

    return dependency


def limit_by_user(scope: str, limit_of: Callable[[Settings], int]) -> Callable[..., None]:
    def dependency(
        user: User = Depends(get_current_user),
        limiter: RateLimiter = Depends(get_limiter),
        settings: Settings = Depends(get_settings),
    ) -> None:
        enforce_rate_limit(limiter, settings, f"{scope}:user:{user.id}", limit_of(settings))

    return dependency
