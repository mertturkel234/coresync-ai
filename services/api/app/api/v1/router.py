"""Version 1 API router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, documents, projects, sessions

api_router = APIRouter(prefix="/v1")
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(documents.router)
api_router.include_router(sessions.router)
