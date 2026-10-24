"""Project, membership and audit services."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.api.deps import RequestContext
from app.core.errors import ConflictError, NotFoundError, ValidationFailedError
from app.models import AuditEvent, Membership, Project, Role, User
from app.repositories import identity as identity_repo
from app.repositories import projects as repo
from app.schemas.auth import AddMemberRequest, MemberOut
from app.schemas.projects import ProjectCreate, ProjectOut, ProjectUpdate
from app.services import access, audit


def _out(project: Project, membership: Membership | None, tenant_name: str | None) -> ProjectOut:
    out = ProjectOut.model_validate(project)
    out.role = membership.role if membership else None
    out.tenant_name = tenant_name
    return out


def create_project(
    db: Session, user: User, payload: ProjectCreate, ctx: RequestContext
) -> ProjectOut:
    membership = access.require_vendor_membership(db, user, payload.tenant_id)
    project = repo.create_project(
        db,
        tenant_id=payload.tenant_id,
        name=payload.name,
        description=payload.description.strip(),
        created_by=user.id,
    )
    audit.record(
        db,
        action="project.create",
        request_id=ctx.request_id,
        actor_user_id=user.id,
        tenant_id=project.tenant_id,
        resource_type="project",
        resource_id=project.id,
        metadata={"name": project.name},
    )
    db.commit()
    tenant_name = next(
        (
            t.name
            for m, t in identity_repo.list_memberships(db, user.id)
            if t.id == project.tenant_id
        ),
        None,
    )
    return _out(project, membership, tenant_name)


def list_projects(db: Session, user: User) -> list[ProjectOut]:
    memberships = identity_repo.list_memberships(db, user.id)
    by_tenant = {t.id: (m, t) for m, t in memberships}
    projects = repo.list_projects_for_tenants(db, list(by_tenant))
    out = []
    for p in projects:
        m, t = by_tenant[p.tenant_id]
        if p.archived and m.role == Role.DEVELOPER.value:
            continue  # developers do not see archived projects
        out.append(_out(p, m, t.name))
    return out


def get_project(db: Session, user: User, project_id: uuid.UUID) -> ProjectOut:
    project, membership = access.get_project_for_user(db, user, project_id)
    if project.archived and membership.role == Role.DEVELOPER.value:
        raise NotFoundError("Resource not found.")
    tenant_name = next(
        (
            t.name
            for m, t in identity_repo.list_memberships(db, user.id)
            if t.id == project.tenant_id
        ),
        None,
    )
    return _out(project, membership, tenant_name)


def update_project(
    db: Session, user: User, project_id: uuid.UUID, payload: ProjectUpdate, ctx: RequestContext
) -> ProjectOut:
    project, membership = access.get_project_for_user(db, user, project_id, vendor_only=True)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        if value is not None:
            setattr(project, key, value.strip() if isinstance(value, str) else value)
    audit.record(
        db,
        action="project.update",
        request_id=ctx.request_id,
        actor_user_id=user.id,
        tenant_id=project.tenant_id,
        resource_type="project",
        resource_id=project.id,
        metadata={"fields": sorted(changes)},
    )
    db.commit()
    return get_project(db, user, project_id)


def add_member(
    db: Session, user: User, tenant_id: uuid.UUID, payload: AddMemberRequest, ctx: RequestContext
) -> MemberOut:
    access.require_owner_membership(db, user, tenant_id)
    target = identity_repo.get_user_by_email(db, payload.email)
    if target is None or not target.is_active:
        raise ValidationFailedError(
            "No registered user with that email. Ask them to create a developer account first.",
            code="user_not_found",
        )
    if identity_repo.get_membership(db, target.id, tenant_id) is not None:
        raise ConflictError("That user is already a member of this organization.")
    identity_repo.add_membership(db, user_id=target.id, tenant_id=tenant_id, role=payload.role)
    audit.record(
        db,
        action="member.add",
        request_id=ctx.request_id,
        actor_user_id=user.id,
        tenant_id=tenant_id,
        resource_type="user",
        resource_id=target.id,
        metadata={"role": payload.role},
    )
    db.commit()
    return MemberOut(
        user_id=target.id, email=target.email, full_name=target.full_name, role=payload.role
    )


def list_members(db: Session, user: User, tenant_id: uuid.UUID) -> list[MemberOut]:
    access.require_vendor_membership(db, user, tenant_id)
    return [
        MemberOut(user_id=u.id, email=u.email, full_name=u.full_name, role=m.role)
        for m, u in identity_repo.list_members(db, tenant_id)
    ]


def list_audit_events(
    db: Session, user: User, tenant_id: uuid.UUID, *, limit: int, offset: int
) -> list[AuditEvent]:
    access.require_vendor_membership(db, user, tenant_id)
    return repo.list_audit_events(db, tenant_id=tenant_id, limit=limit, offset=offset)
