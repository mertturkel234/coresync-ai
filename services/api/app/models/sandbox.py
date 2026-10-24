"""Sandbox credentials and test runs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin, UTCDateTime


class SandboxCredential(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "sandbox_credentials"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("integration_sessions.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    # Public, non-secret identifier ("csk_<public_id>"); the secret part is never stored.
    token_prefix: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="demo")
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    max_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class TestRun(Base, IdMixin, CreatedAtMixin):
    """The recorded outcome of an executed request plan (never a generated-only result)."""

    __test__ = False  # not a pytest test class
    __tablename__ = "test_runs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("integration_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code_example_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("code_examples.id", ondelete="CASCADE"), index=True, nullable=False
    )
    credential_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sandbox_credentials.id", ondelete="SET NULL"), nullable=True
    )
    executed_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    runner: Mapped[str] = mapped_column(String(40), nullable=False)
    # passed | failed | error | timeout
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    response_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output_truncated: Mapped[bool] = mapped_column(nullable=False, default=False)
    diagnostics: Mapped[str] = mapped_column(Text, nullable=False, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
