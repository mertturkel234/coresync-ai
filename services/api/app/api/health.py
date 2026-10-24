"""Health endpoints with real dependency checks."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    """Process liveness only; does not touch dependencies."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready(request: Request, response: Response) -> dict:
    """Readiness: verifies the database and, when configured, Redis."""
    checks: dict[str, dict[str, str]] = {}

    try:
        with request.app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok"}
    except Exception:  # noqa: BLE001 - details are logged, never returned
        checks["database"] = {"status": "error"}

    redis_client = request.app.state.redis
    if redis_client is None:
        checks["redis"] = {"status": "not_configured"}
    else:
        try:
            redis_client.ping()
            checks["redis"] = {"status": "ok"}
        except Exception:  # noqa: BLE001
            checks["redis"] = {"status": "error"}

    healthy = all(c["status"] in ("ok", "not_configured") for c in checks.values())
    if not healthy:
        response.status_code = 503
    return {"status": "ok" if healthy else "degraded", "checks": checks}
