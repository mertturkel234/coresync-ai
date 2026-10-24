"""Integration session and AI Q&A endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import RequestContext, get_ctx, get_current_user, get_settings, limit_by_user
from app.core.config import Settings
from app.db.session import get_db
from app.models import User
from app.schemas.sessions import (
    AskQuestionRequest,
    AskQuestionResponse,
    SessionCreate,
    SessionDetailOut,
    SessionOut,
)
from app.services import chat as service

router = APIRouter(tags=["sessions"])

_ai_limit = limit_by_user("ai", lambda s: s.rate_limit_ai_per_window)


@router.post("/projects/{project_id}/sessions", response_model=SessionOut, status_code=201)
def create_session(
    project_id: uuid.UUID,
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_ctx),
) -> SessionOut:
    return service.create_session(db, user, project_id, payload, ctx)


@router.get("/projects/{project_id}/sessions", response_model=list[SessionOut])
def list_sessions(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionOut]:
    return service.list_sessions(db, user, project_id)


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionDetailOut:
    return service.get_session_detail(db, user, session_id)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=AskQuestionResponse,
    status_code=201,
    dependencies=[Depends(_ai_limit)],
)
def ask_question(
    session_id: uuid.UUID,
    payload: AskQuestionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ctx: RequestContext = Depends(get_ctx),
) -> AskQuestionResponse:
    return service.ask_question(
        db, settings=settings, user=user, session_id=session_id, payload=payload, ctx=ctx
    )
