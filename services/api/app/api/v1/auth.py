"""Authentication endpoints."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    RequestContext,
    enforce_rate_limit,
    get_ctx,
    get_current_user,
    get_limiter,
    get_settings,
    limit_by_ip,
)
from app.core.config import Settings
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, MeResponse, RegisterRequest, TokenResponse, UserOut
from app.security.ratelimit import RateLimiter
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

_ip_limit = limit_by_ip("auth", lambda s: s.rate_limit_auth_per_window)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(_ip_limit)],
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ctx: RequestContext = Depends(get_ctx),
) -> TokenResponse:
    user = auth_service.register(db, settings, payload, ctx)
    return auth_service.token_response(db, settings, user)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(_ip_limit)])
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    limiter: RateLimiter = Depends(get_limiter),
    ctx: RequestContext = Depends(get_ctx),
) -> TokenResponse:
    # Per-account throttle (in addition to per-IP) slows credential stuffing against one email.
    fingerprint = hashlib.sha256(payload.email.strip().lower().encode()).hexdigest()[:24]
    enforce_rate_limit(
        limiter, settings, f"login:acct:{fingerprint}", settings.rate_limit_auth_per_window
    )
    user = auth_service.authenticate(db, payload.email, payload.password, ctx)
    return auth_service.token_response(db, settings, user)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    return MeResponse(
        user=UserOut.model_validate(user), memberships=auth_service.memberships_out(db, user)
    )
