"""Integration sessions, chat messages and generated code examples."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin


class IntegrationSession(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "integration_sessions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)


class Message(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "messages"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("integration_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    references: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    # How the assistant text was produced: "offline" (deterministic, extractive) or "llm".
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    grounded: Mapped[bool | None] = mapped_column(nullable=True)
    code_example_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class CodeExample(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "code_examples"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("integration_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="python")
    code: Mapped[str] = mapped_column(Text, nullable=False)
    code_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    request_plan: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
