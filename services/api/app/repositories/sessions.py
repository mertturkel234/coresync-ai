"""Persistence for integration sessions, messages and code examples."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CodeExample, IntegrationSession, Message


def create_session(
    db: Session, *, tenant_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID, title: str
) -> IntegrationSession:
    session = IntegrationSession(
        tenant_id=tenant_id, project_id=project_id, user_id=user_id, title=title
    )
    db.add(session)
    db.flush()
    return session


def get_session(
    db: Session, *, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> IntegrationSession | None:
    return db.scalar(
        select(IntegrationSession).where(
            IntegrationSession.id == session_id, IntegrationSession.tenant_id == tenant_id
        )
    )


def list_sessions_for_project(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> list[IntegrationSession]:
    stmt = select(IntegrationSession).where(
        IntegrationSession.tenant_id == tenant_id,
        IntegrationSession.project_id == project_id,
    )
    if user_id is not None:
        stmt = stmt.where(IntegrationSession.user_id == user_id)
    return list(db.scalars(stmt.order_by(IntegrationSession.created_at.desc())))


def add_message(db: Session, msg: Message) -> Message:
    db.add(msg)
    db.flush()
    return msg


def list_messages(db: Session, *, tenant_id: uuid.UUID, session_id: uuid.UUID) -> list[Message]:
    return list(
        db.scalars(
            select(Message)
            .where(Message.tenant_id == tenant_id, Message.session_id == session_id)
            .order_by(Message.created_at, Message.id)
        )
    )


def add_code_example(db: Session, example: CodeExample) -> CodeExample:
    db.add(example)
    db.flush()
    return example


def get_code_example(
    db: Session, *, tenant_id: uuid.UUID, example_id: uuid.UUID
) -> CodeExample | None:
    return db.scalar(
        select(CodeExample).where(CodeExample.id == example_id, CodeExample.tenant_id == tenant_id)
    )


def list_code_examples(
    db: Session, *, tenant_id: uuid.UUID, session_id: uuid.UUID
) -> list[CodeExample]:
    return list(
        db.scalars(
            select(CodeExample)
            .where(CodeExample.tenant_id == tenant_id, CodeExample.session_id == session_id)
            .order_by(CodeExample.created_at.desc())
        )
    )
