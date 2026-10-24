"""Projects, documents and the retrieval index."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, IdMixin, UTCDateTime


class DocType(enum.StrEnum):
    OPENAPI_JSON = "openapi_json"
    OPENAPI_YAML = "openapi_yaml"
    MARKDOWN = "markdown"


class DocStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class Project(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "projects"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)


class Document(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("project_id", "filename", "version"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # sanitized display name
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=DocStatus.PENDING.value)
    validation_errors: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    api_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    server_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    endpoint_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Endpoint(Base, IdMixin, CreatedAtMixin):
    __tablename__ = "endpoints"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    operation_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tags: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    parameters: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    request_body: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    responses: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    security: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="openapi")


class DocChunk(Base, IdMixin, CreatedAtMixin):
    """A retrieval unit with a human-readable reference."""

    __tablename__ = "doc_chunks"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    endpoint_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("endpoints.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # endpoint | schema | section
    ref: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
