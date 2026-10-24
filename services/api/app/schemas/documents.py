"""Document and extracted endpoint schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    version: int
    doc_type: str
    size_bytes: int
    sha256: str
    status: str
    validation_errors: list[str]
    title: str | None
    api_version: str | None
    server_url: str | None
    endpoint_count: int
    uploaded_by: uuid.UUID
    processed_at: datetime | None
    created_at: datetime


class EndpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    document_id: uuid.UUID
    method: str
    path: str
    operation_id: str | None
    summary: str
    description: str
    tags: list[str]
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any] | None
    responses: dict[str, Any]
    security: list[dict[str, Any]]
    source: str
    created_at: datetime
