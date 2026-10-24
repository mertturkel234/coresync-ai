"""Schemas for integration sessions, chat messages and generated code examples."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionCreate(BaseModel):
    title: str = Field(default="Integration session", min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be blank")
        return v


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime


class ReferenceOut(BaseModel):
    ref: str
    title: str
    kind: str
    document_id: uuid.UUID
    endpoint_id: uuid.UUID | None = None
    score: float


class CodeExampleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    session_id: uuid.UUID
    endpoint_id: uuid.UUID
    language: str
    code: str
    code_sha256: str
    request_plan: dict[str, Any]
    created_at: datetime
    execution_state: str = "not_executed"


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    references: list[ReferenceOut]
    mode: str | None
    grounded: bool | None
    code_example_id: uuid.UUID | None
    created_at: datetime


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    endpoint_id: uuid.UUID | None = None
    generate_code: bool = True

    @field_validator("question")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("question must be at least 2 characters")
        return v


class AskQuestionResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
    code_example: CodeExampleOut | None = None


class SessionDetailOut(BaseModel):
    session: SessionOut
    messages: list[MessageOut]
    code_examples: list[CodeExampleOut]
