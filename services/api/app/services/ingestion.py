"""Controlled documentation ingestion pipeline."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.ai.markdown import MarkdownValidationError, parse_markdown
from app.ai.openapi import ChunkSpec, EndpointSpec, OpenAPIValidationError, parse_openapi
from app.api.deps import RequestContext
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.db.base import utcnow
from app.models import DocChunk, DocStatus, DocType, Document, Endpoint, User
from app.repositories import documents as repo
from app.services import access, audit, storage


def ingest_document(
    db: Session,
    *,
    settings: Settings,
    user: User,
    project_id: uuid.UUID,
    raw_filename: str | None,
    raw_bytes: bytes,
    ctx: RequestContext,
) -> Document:
    project, _ = access.get_project_for_user(db, user, project_id, vendor_only=True)
    filename, doc_type = storage.sanitize_filename(raw_filename)
    text, sha256 = storage.validate_and_decode_bytes(raw_bytes, max_bytes=settings.max_upload_bytes)
    storage_key = storage.store_document_bytes(settings.storage_dir, project.tenant_id, raw_bytes)
    version = repo.next_version(
        db, tenant_id=project.tenant_id, project_id=project.id, filename=filename
    )

    doc = Document(
        tenant_id=project.tenant_id,
        project_id=project.id,
        filename=filename,
        version=version,
        doc_type=doc_type.value,
        size_bytes=len(raw_bytes),
        sha256=sha256,
        storage_key=storage_key,
        status=DocStatus.PROCESSING.value,
        uploaded_by=user.id,
    )
    repo.create_document(db, doc)
    audit.record(
        db,
        action="document.upload",
        request_id=ctx.request_id,
        actor_user_id=user.id,
        tenant_id=project.tenant_id,
        resource_type="document",
        resource_id=doc.id,
        metadata={"filename": filename, "doc_type": doc_type.value, "version": version},
    )

    try:
        if doc_type in (DocType.OPENAPI_JSON, DocType.OPENAPI_YAML):
            parsed = parse_openapi(
                text,
                is_yaml=(doc_type == DocType.OPENAPI_YAML),
                max_endpoints=settings.max_endpoints_per_document,
            )
            doc.title = parsed.title
            doc.api_version = parsed.api_version
            doc.server_url = parsed.server_url
            endpoint_specs = parsed.endpoints
            chunk_specs = parsed.chunks
        else:
            parsed_md = parse_markdown(text, filename=filename)
            doc.title = parsed_md.title
            endpoint_specs = parsed_md.endpoints
            chunk_specs = parsed_md.chunks

        _persist_extracted(
            db,
            tenant_id=project.tenant_id,
            project_id=project.id,
            document_id=doc.id,
            endpoint_specs=endpoint_specs,
            chunk_specs=chunk_specs,
        )
        doc.endpoint_count = len(endpoint_specs)
        doc.status = DocStatus.PROCESSED.value
        doc.validation_errors = []
        doc.processed_at = utcnow()
        audit.record(
            db,
            action="document.processed",
            request_id=ctx.request_id,
            actor_user_id=user.id,
            tenant_id=project.tenant_id,
            resource_type="document",
            resource_id=doc.id,
            metadata={"endpoint_count": doc.endpoint_count, "chunk_count": len(chunk_specs)},
        )
    except (OpenAPIValidationError, MarkdownValidationError) as exc:
        doc.status = DocStatus.FAILED.value
        doc.validation_errors = exc.errors
        doc.processed_at = utcnow()
        audit.record(
            db,
            action="document.failed",
            request_id=ctx.request_id,
            actor_user_id=user.id,
            tenant_id=project.tenant_id,
            resource_type="document",
            resource_id=doc.id,
            outcome="failure",
            metadata={"errors": exc.errors[:10]},
        )

    db.commit()
    return doc


def _persist_extracted(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    endpoint_specs: list[EndpointSpec],
    chunk_specs: list[ChunkSpec],
) -> None:
    endpoint_models: list[Endpoint] = []
    by_key: dict[tuple[str, str], Endpoint] = {}
    for spec in endpoint_specs:
        ep = Endpoint(
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=document_id,
            method=spec.method,
            path=spec.path,
            operation_id=spec.operation_id,
            summary=spec.summary,
            description=spec.description,
            tags=spec.tags,
            parameters=spec.parameters,
            request_body=spec.request_body,
            responses=spec.responses,
            security=spec.security,
            source=spec.source,
        )
        endpoint_models.append(ep)
        by_key[(spec.method, spec.path)] = ep

    for ep in endpoint_models:
        db.add(ep)
    db.flush()

    chunk_models = [
        DocChunk(
            tenant_id=tenant_id,
            project_id=project_id,
            document_id=document_id,
            endpoint_id=by_key[cs.endpoint_key].id if cs.endpoint_key in by_key else None,
            kind=cs.kind,
            ref=cs.ref,
            title=cs.title,
            content=cs.content,
        )
        for cs in chunk_specs
    ]
    repo.add_endpoints_and_chunks(db, endpoints=[], chunks=chunk_models)


def list_documents(db: Session, user: User, project_id: uuid.UUID) -> list[Document]:
    project, _ = access.get_project_for_user(db, user, project_id)
    return repo.list_documents(db, tenant_id=project.tenant_id, project_id=project.id)


def get_document(
    db: Session, user: User, project_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
    project, _ = access.get_project_for_user(db, user, project_id)
    doc = repo.get_document(
        db, tenant_id=project.tenant_id, project_id=project.id, document_id=document_id
    )
    if doc is None:
        raise NotFoundError("Document not found.")
    return doc


def list_endpoints(db: Session, user: User, project_id: uuid.UUID) -> list[Endpoint]:
    project, _ = access.get_project_for_user(db, user, project_id)
    return repo.list_endpoints(db, tenant_id=project.tenant_id, project_id=project.id)


def get_endpoint(
    db: Session, user: User, project_id: uuid.UUID, endpoint_id: uuid.UUID
) -> Endpoint:
    project, _ = access.get_project_for_user(db, user, project_id)
    ep = repo.get_endpoint(
        db, tenant_id=project.tenant_id, project_id=project.id, endpoint_id=endpoint_id
    )
    if ep is None:
        raise NotFoundError("Endpoint not found.")
    return ep
