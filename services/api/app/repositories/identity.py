"""User, tenant and membership persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Membership, Tenant, User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def get_user(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, *, email: str, password_hash: str, full_name: str) -> User:
    user = User(email=normalize_email(email), password_hash=password_hash, full_name=full_name)
    db.add(user)
    db.flush()
    return user


def create_tenant(db: Session, name: str) -> Tenant:
    tenant = Tenant(name=name)
    db.add(tenant)
    db.flush()
    return tenant


def add_membership(
    db: Session, *, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str
) -> Membership:
    membership = Membership(user_id=user_id, tenant_id=tenant_id, role=role)
    db.add(membership)
    db.flush()
    return membership


def get_membership(db: Session, user_id: uuid.UUID, tenant_id: uuid.UUID) -> Membership | None:
    return db.scalar(
        select(Membership).where(Membership.user_id == user_id, Membership.tenant_id == tenant_id)
    )


def list_memberships(db: Session, user_id: uuid.UUID) -> list[tuple[Membership, Tenant]]:
    rows = db.execute(
        select(Membership, Tenant)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(Membership.user_id == user_id)
        .order_by(Tenant.name)
    ).all()
    return [(m, t) for m, t in rows]


def list_members(db: Session, tenant_id: uuid.UUID) -> list[tuple[Membership, User]]:
    rows = db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.tenant_id == tenant_id)
        .order_by(User.email)
    ).all()
    return [(m, u) for m, u in rows]
