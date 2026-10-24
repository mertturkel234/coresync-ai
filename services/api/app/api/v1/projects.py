"""Projects, organization members and audit log endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import RequestContext, get_ctx, get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas.auth import AddMemberRequest, MemberOut
from app.schemas.projects import AuditEventOut, ProjectCreate, ProjectOut, ProjectUpdate
from app.services import projects as service

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_ctx),
) -> ProjectOut:
    return service.create_project(db, user, payload, ctx)


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ProjectOut]:
    return service.list_projects(db, user)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProjectOut:
    return service.get_project(db, user, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_ctx),
) -> ProjectOut:
    return service.update_project(db, user, project_id, payload, ctx)


@router.get("/tenants/{tenant_id}/members", response_model=list[MemberOut])
def list_members(
    tenant_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[MemberOut]:
    return service.list_members(db, user, tenant_id)


@router.post("/tenants/{tenant_id}/members", response_model=MemberOut, status_code=201)
def add_member(
    tenant_id: uuid.UUID,
    payload: AddMemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_ctx),
) -> MemberOut:
    return service.add_member(db, user, tenant_id, payload, ctx)


@router.get("/tenants/{tenant_id}/audit-events", response_model=list[AuditEventOut])
def list_audit_events(
    tenant_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AuditEventOut]:
    events = service.list_audit_events(db, user, tenant_id, limit=limit, offset=offset)
    return [AuditEventOut.model_validate(e) for e in events]
