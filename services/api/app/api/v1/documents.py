"""Document upload, status inspection and extracted endpoint APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import RequestContext, get_ctx, get_current_user, get_settings
from app.core.config import Settings
from app.db.session import get_db
from app.models import DocStatus, User
from app.schemas.documents import DocumentOut, EndpointOut
from app.services import ingestion

router = APIRouter(prefix="/projects/{project_id}", tags=["documents"])


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    project_id: uuid.UUID,
    response: Response,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ctx: RequestContext = Depends(get_ctx),
) -> DocumentOut:
    # Read at most max_upload_bytes + 1 so oversized payloads are bounded in memory.
    raw = await file.read(settings.max_upload_bytes + 1)
    doc = ingestion.ingest_document(
        db,
        settings=settings,
        user=user,
        project_id=project_id,
        raw_filename=file.filename,
        raw_bytes=raw,
        ctx=ctx,
    )
    if doc.status == DocStatus.FAILED.value:
        response.status_code = 422
    return DocumentOut.model_validate(doc)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    docs = ingestion.list_documents(db, user, project_id)
    return [DocumentOut.model_validate(d) for d in docs]


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    doc = ingestion.get_document(db, user, project_id, document_id)
    return DocumentOut.model_validate(doc)


@router.get("/endpoints", response_model=list[EndpointOut])
def list_endpoints(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EndpointOut]:
    endpoints = ingestion.list_endpoints(db, user, project_id)
    return [EndpointOut.model_validate(e) for e in endpoints]


@router.get("/endpoints/{endpoint_id}", response_model=EndpointOut)
def get_endpoint(
    project_id: uuid.UUID,
    endpoint_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EndpointOut:
    ep = ingestion.get_endpoint(db, user, project_id, endpoint_id)
    return EndpointOut.model_validate(ep)
