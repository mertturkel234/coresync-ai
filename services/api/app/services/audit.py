"""Audit logging. Metadata and detail are scrubbed so raw secrets are never stored."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.repositories import projects as repo
from app.security.redaction import redact_text, scrub


def record(
    db: Session,
    *,
    action: str,
    request_id: str | None,
    actor_user_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | str | None = None,
    outcome: str = "success",
    detail: str = "",
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Stage an audit event in the caller's transaction (the caller commits)."""
    event = AuditEvent(
        action=action,
        outcome=outcome,
        actor_user_id=actor_user_id,
        tenant_id=tenant_id,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        request_id=request_id,
        detail=redact_text(detail)[:2000],
        event_metadata=scrub(metadata or {}),
    )
    return repo.add_audit_event(db, event)
