"""Registration, login and token issuance."""

from __future__ import annotations

import hashlib

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import RequestContext
from app.core.config import Settings
from app.core.errors import AuthenticationError, ConflictError
from app.db.base import utcnow
from app.models import Role, User
from app.repositories import identity as repo
from app.schemas.auth import MembershipOut, RegisterRequest, TokenResponse, UserOut
from app.security import passwords
from app.security.tokens import create_access_token
from app.services import audit


def _email_fingerprint(email: str) -> str:
    return hashlib.sha256(repo.normalize_email(email).encode()).hexdigest()[:16]


def memberships_out(db: Session, user: User) -> list[MembershipOut]:
    return [
        MembershipOut(tenant_id=t.id, tenant_name=t.name, role=m.role)
        for m, t in repo.list_memberships(db, user.id)
    ]


def token_response(db: Session, settings: Settings, user: User) -> TokenResponse:
    token, expires_in = create_access_token(settings, user.id)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
        memberships=memberships_out(db, user),
    )


def register(
    db: Session, settings: Settings, payload: RegisterRequest, ctx: RequestContext
) -> User:
    if repo.get_user_by_email(db, payload.email) is not None:
        raise ConflictError("An account with this email already exists.", code="email_taken")
    try:
        user = repo.create_user(
            db,
            email=payload.email,
            password_hash=passwords.hash_password(payload.password),
            full_name=payload.full_name,
        )
        tenant_id = None
        if payload.account_type == "vendor":
            tenant = repo.create_tenant(db, payload.organization_name or "")
            repo.add_membership(db, user_id=user.id, tenant_id=tenant.id, role=Role.OWNER.value)
            tenant_id = tenant.id
        audit.record(
            db,
            action="auth.register",
            request_id=ctx.request_id,
            actor_user_id=user.id,
            tenant_id=tenant_id,
            resource_type="user",
            resource_id=user.id,
            metadata={"account_type": payload.account_type},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            "An account with this email already exists.", code="email_taken"
        ) from None
    return user


def authenticate(db: Session, email: str, password: str, ctx: RequestContext) -> User:
    user = repo.get_user_by_email(db, email)
    if user is None:
        passwords.verify_dummy(password)  # equalize timing
        valid = False
    else:
        valid = passwords.verify_password(user.password_hash, password) and user.is_active
    if not valid or user is None:
        audit.record(
            db,
            action="auth.login_failed",
            request_id=ctx.request_id,
            actor_user_id=user.id if user else None,
            outcome="failure",
            metadata={"email_fingerprint": _email_fingerprint(email)},
        )
        db.commit()
        raise AuthenticationError("Invalid email or password.")
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(password)
    user.last_login_at = utcnow()
    audit.record(
        db,
        action="auth.login",
        request_id=ctx.request_id,
        actor_user_id=user.id,
        resource_type="user",
        resource_id=user.id,
    )
    db.commit()
    return user
