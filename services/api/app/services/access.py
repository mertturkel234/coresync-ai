"""Authorization helpers. Cross-tenant access answers 404 so resource existence is not leaked."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, PermissionDeniedError
from app.models import VENDOR_ROLES, Membership, Project, Role, User
from app.repositories import identity as identity_repo
from app.repositories import projects as projects_repo


def is_vendor(membership: Membership) -> bool:
    return membership.role in {r.value for r in VENDOR_ROLES}


def require_membership(db: Session, user: User, tenant_id: uuid.UUID) -> Membership:
    membership = identity_repo.get_membership(db, user.id, tenant_id)
    if membership is None:
        raise NotFoundError("Resource not found.")
    return membership


def require_vendor_membership(db: Session, user: User, tenant_id: uuid.UUID) -> Membership:
    membership = require_membership(db, user, tenant_id)
    if not is_vendor(membership):
        raise PermissionDeniedError("This action requires a vendor role.")
    return membership


def require_owner_membership(db: Session, user: User, tenant_id: uuid.UUID) -> Membership:
    membership = require_membership(db, user, tenant_id)
    if membership.role != Role.OWNER.value:
        raise PermissionDeniedError("This action requires the owner role.")
    return membership


def get_project_for_user(
    db: Session, user: User, project_id: uuid.UUID, *, vendor_only: bool = False
) -> tuple[Project, Membership]:
    """Load a project the user may access, or raise NotFoundError (never reveal other tenants)."""
    project = projects_repo.get_project(db, project_id)
    if project is None:
        raise NotFoundError("Resource not found.")
    membership = require_membership(db, user, project.tenant_id)
    if vendor_only and not is_vendor(membership):
        raise PermissionDeniedError("This action requires a vendor role.")
    return project, membership
