"""Centralized error types and handlers.

All error responses share one envelope:
    {"error": {"code": str, "message": str, "details": any | null, "request_id": str}}
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("coresync.errors")

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


def new_request_id(incoming: str | None = None) -> str:
    """Accept a well-formed client request id, otherwise generate one (never trust raw input)."""
    if incoming and _SAFE_REQUEST_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or new_request_id()


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: Any = None, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"

    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(message)


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthenticated"

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(message)


class PermissionDeniedError(AppError):
    status_code = 403
    code = "forbidden"

    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(message)


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_failed"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(
        self, message: str = "Too many requests. Please retry later.", *, retry_after: int = 60
    ):
        super().__init__(message)
        self.retry_after = retry_after


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = get_request_id(request)
    out_headers = {REQUEST_ID_HEADER: request_id}
    if headers:
        out_headers.update(headers)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id,
            }
        },
        headers=out_headers,
    )


def _clean_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Drop 'input' and 'ctx' so submitted values (possibly secrets) are never echoed back.
    return [
        {
            "loc": [str(p) for p in e.get("loc", [])],
            "msg": e.get("msg", ""),
            "type": e.get("type", ""),
        }
        for e in errors
    ]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        headers = None
        if isinstance(exc, RateLimitedError):
            headers = {"Retry-After": str(exc.retry_after)}
        if isinstance(exc, AuthenticationError):
            headers = {"WWW-Authenticate": "Bearer"}
        return error_response(request, exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            request,
            422,
            "validation_failed",
            "The request is invalid.",
            _clean_validation_errors(list(exc.errors())),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return error_response(request, exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = get_request_id(request)
        # Full details go to server logs only; the client gets a generic message + request id.
        logger.error(
            "Unhandled error request_id=%s path=%s", request_id, request.url.path, exc_info=exc
        )
        return error_response(
            request,
            500,
            "internal_error",
            "An unexpected error occurred. Quote the request_id when contacting support.",
        )
