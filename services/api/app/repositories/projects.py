"""Project and audit persistence. Every tenant-owned query requires the tenant scope."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Project


def create_project(
    db: Session, *, tenant_id: uuid.UUID, name: str, description: str, created_by: uuid.UUID
) -> Project:
    project = Project(
        tenant_id=tenant_id, name=name, description=description, created_by=created_by
    )
    db.add(project)
    db.flush()
    return project


def get_project(db: Session, project_id: uuid.UUID) -> Project | None:
    return db.get(Project, project_id)


def list_projects_for_tenants(db: Session, tenant_ids: list[uuid.UUID]) -> list[Project]:
    if not tenant_ids:
        return []
    return list(
        db.scalars(
            select(Project)
            .where(Project.tenant_id.in_(tenant_ids))
            .order_by(Project.created_at.desc())
        )
    )


def add_audit_event(db: Session, event: AuditEvent) -> AuditEvent:
    db.add(event)
    db.flush()
    return event


def list_audit_events(
    db: Session, *, tenant_id: uuid.UUID, limit: int, offset: int
) -> list[AuditEvent]:
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
            .limit(limit)
            .offset(offset)
        )
    )
