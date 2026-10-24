"""Document, endpoint and chunk persistence (always tenant- and project-scoped)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DocChunk, Document, Endpoint


def next_version(db: Session, *, tenant_id: uuid.UUID, project_id: uuid.UUID, filename: str) -> int:
    current = db.scalar(
        select(func.max(Document.version)).where(
            Document.tenant_id == tenant_id,
            Document.project_id == project_id,
            Document.filename == filename,
        )
    )
    return int(current or 0) + 1


def create_document(db: Session, doc: Document) -> Document:
    db.add(doc)
    db.flush()
    return doc


def get_document(
    db: Session, *, tenant_id: uuid.UUID, project_id: uuid.UUID, document_id: uuid.UUID
) -> Document | None:
    return db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.project_id == project_id,
        )
    )


def list_documents(db: Session, *, tenant_id: uuid.UUID, project_id: uuid.UUID) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(Document.tenant_id == tenant_id, Document.project_id == project_id)
            .order_by(Document.created_at.desc(), Document.version.desc())
        )
    )


def add_endpoints_and_chunks(
    db: Session, *, endpoints: list[Endpoint], chunks: list[DocChunk]
) -> None:
    for ep in endpoints:
        db.add(ep)
    db.flush()
    for ch in chunks:
        db.add(ch)
    db.flush()


def list_endpoints(db: Session, *, tenant_id: uuid.UUID, project_id: uuid.UUID) -> list[Endpoint]:
    return list(
        db.scalars(
            select(Endpoint)
            .where(Endpoint.tenant_id == tenant_id, Endpoint.project_id == project_id)
            .order_by(Endpoint.path, Endpoint.method)
        )
    )


def get_endpoint(
    db: Session, *, tenant_id: uuid.UUID, project_id: uuid.UUID, endpoint_id: uuid.UUID
) -> Endpoint | None:
    return db.scalar(
        select(Endpoint).where(
            Endpoint.id == endpoint_id,
            Endpoint.tenant_id == tenant_id,
            Endpoint.project_id == project_id,
        )
    )


def list_chunks(db: Session, *, tenant_id: uuid.UUID, project_id: uuid.UUID) -> list[DocChunk]:
    return list(
        db.scalars(
            select(DocChunk)
            .where(DocChunk.tenant_id == tenant_id, DocChunk.project_id == project_id)
            .order_by(DocChunk.created_at)
        )
    )
