"""Integration session management, grounded Q&A and Python code generation."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.ai.codegen import generate_python_example
from app.ai.providers import LLMProvider, get_llm_provider
from app.ai.retrieval import retrieve_chunks
from app.api.deps import RequestContext
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.models import CodeExample, Endpoint, IntegrationSession, Membership, Message, User
from app.repositories import documents as docs_repo
from app.repositories import identity as identity_repo
from app.repositories import sessions as repo
from app.schemas.sessions import (
    AskQuestionRequest,
    AskQuestionResponse,
    CodeExampleOut,
    MessageOut,
    SessionCreate,
    SessionDetailOut,
    SessionOut,
)
from app.services import access, audit


def get_session_for_user(
    db: Session, user: User, session_id: uuid.UUID
) -> tuple[IntegrationSession, Membership]:
    memberships = identity_repo.list_memberships(db, user.id)
    by_tenant = {t.id: m for m, t in memberships}
    for tenant_id, membership in by_tenant.items():
        session = repo.get_session(db, tenant_id=tenant_id, session_id=session_id)
        if session is not None:
            # Developers only access their own sessions; vendors may review all in tenant.
            if not access.is_vendor(membership) and session.user_id != user.id:
                raise NotFoundError("Session not found.")
            return session, membership
    raise NotFoundError("Session not found.")


def create_session(
    db: Session, user: User, project_id: uuid.UUID, payload: SessionCreate, ctx: RequestContext
) -> SessionOut:
    project, _ = access.get_project_for_user(db, user, project_id)
    session = repo.create_session(
        db,
        tenant_id=project.tenant_id,
        project_id=project.id,
        user_id=user.id,
        title=payload.title,
    )
    audit.record(
        db,
        action="session.create",
        request_id=ctx.request_id,
        actor_user_id=user.id,
        tenant_id=project.tenant_id,
        resource_type="session",
        resource_id=session.id,
        metadata={"project_id": str(project.id), "title": session.title},
    )
    db.commit()
    return SessionOut.model_validate(session)


def list_sessions(db: Session, user: User, project_id: uuid.UUID) -> list[SessionOut]:
    project, membership = access.get_project_for_user(db, user, project_id)
    owner_filter = None if access.is_vendor(membership) else user.id
    sessions = repo.list_sessions_for_project(
        db, tenant_id=project.tenant_id, project_id=project.id, user_id=owner_filter
    )
    return [SessionOut.model_validate(s) for s in sessions]


def get_session_detail(db: Session, user: User, session_id: uuid.UUID) -> SessionDetailOut:
    session, _ = get_session_for_user(db, user, session_id)
    messages = repo.list_messages(db, tenant_id=session.tenant_id, session_id=session.id)
    examples = repo.list_code_examples(db, tenant_id=session.tenant_id, session_id=session.id)
    return SessionDetailOut(
        session=SessionOut.model_validate(session),
        messages=[MessageOut.model_validate(m) for m in messages],
        code_examples=[CodeExampleOut.model_validate(e) for e in examples],
    )


def ask_question(
    db: Session,
    *,
    settings: Settings,
    user: User,
    session_id: uuid.UUID,
    payload: AskQuestionRequest,
    ctx: RequestContext,
    provider: LLMProvider | None = None,
) -> AskQuestionResponse:
    session, _ = get_session_for_user(db, user, session_id)
    selected_endpoint: Endpoint | None = None
    if payload.endpoint_id is not None:
        selected_endpoint = docs_repo.get_endpoint(
            db,
            tenant_id=session.tenant_id,
            project_id=session.project_id,
            endpoint_id=payload.endpoint_id,
        )
        if selected_endpoint is None:
            raise NotFoundError("Endpoint not found in this project.")

    user_msg = repo.add_message(
        db,
        Message(
            tenant_id=session.tenant_id,
            session_id=session.id,
            role="user",
            content=payload.question,
            references=[],
        ),
    )

    retrieval = retrieve_chunks(
        db,
        tenant_id=session.tenant_id,
        project_id=session.project_id,
        query=payload.question,
        preferred_endpoint_id=payload.endpoint_id,
    )

    llm = provider or get_llm_provider(settings)
    if not retrieval.sufficient:
        answer_text = (
            "The uploaded documentation for this project does not contain sufficient information "
            "to answer that question or verify a matching endpoint. Upload or select a documented "
            "API endpoint before generating integration code."
        )
        assistant_msg = repo.add_message(
            db,
            Message(
                tenant_id=session.tenant_id,
                session_id=session.id,
                role="assistant",
                content=answer_text,
                references=[],
                mode="offline" if settings.llm_provider == "offline" else "llm",
                grounded=False,
                code_example_id=None,
            ),
        )
        db.commit()
        return AskQuestionResponse(
            user_message=MessageOut.model_validate(user_msg),
            assistant_message=MessageOut.model_validate(assistant_msg),
            code_example=None,
        )

    llm_res = llm.generate(payload.question, retrieval.chunks)
    references = [
        {
            "ref": sc.chunk.ref,
            "title": sc.chunk.title,
            "kind": sc.chunk.kind,
            "document_id": str(sc.chunk.document_id),
            "endpoint_id": str(sc.chunk.endpoint_id) if sc.chunk.endpoint_id else None,
            "score": sc.score,
        }
        for sc in retrieval.chunks
    ]

    target_endpoint = selected_endpoint
    if target_endpoint is None and payload.generate_code:
        for sc in retrieval.chunks:
            if sc.chunk.endpoint_id is not None:
                target_endpoint = docs_repo.get_endpoint(
                    db,
                    tenant_id=session.tenant_id,
                    project_id=session.project_id,
                    endpoint_id=sc.chunk.endpoint_id,
                )
                if target_endpoint is not None:
                    break

    code_example_out: CodeExampleOut | None = None
    code_example_id: uuid.UUID | None = None
    if payload.generate_code and target_endpoint is not None:
        code, code_sha256, plan = generate_python_example(target_endpoint)
        example = repo.add_code_example(
            db,
            CodeExample(
                tenant_id=session.tenant_id,
                project_id=session.project_id,
                session_id=session.id,
                endpoint_id=target_endpoint.id,
                language="python",
                code=code,
                code_sha256=code_sha256,
                request_plan=plan,
            ),
        )
        code_example_id = example.id
        code_example_out = CodeExampleOut.model_validate(example)

    assistant_msg = repo.add_message(
        db,
        Message(
            tenant_id=session.tenant_id,
            session_id=session.id,
            role="assistant",
            content=llm_res.content,
            references=references,
            mode=llm_res.mode,
            grounded=True,
            code_example_id=code_example_id,
        ),
    )
    audit.record(
        db,
        action="ai.ask",
        request_id=ctx.request_id,
        actor_user_id=user.id,
        tenant_id=session.tenant_id,
        resource_type="session",
        resource_id=session.id,
        metadata={
            "mode": llm_res.mode,
            "reference_count": len(references),
            "code_generated": code_example_id is not None,
        },
    )
    db.commit()
    return AskQuestionResponse(
        user_message=MessageOut.model_validate(user_msg),
        assistant_message=MessageOut.model_validate(assistant_msg),
        code_example=code_example_out,
    )
