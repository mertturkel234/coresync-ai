from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.security.redaction import REDACTED, redact_text, scrub


def test_validation_error_does_not_echo_sensitive_input(client: TestClient) -> None:
    secret_pw = "short-pw"
    r = client.post(
        "/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": secret_pw,
            "full_name": "User",
            "account_type": "developer",
        },
    )
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_failed"
    assert err["request_id"]
    assert secret_pw not in r.text


def test_unhandled_exception_returns_generic_500_without_stack_trace(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/boom")
    def _boom() -> None:
        raise RuntimeError("database password=super-secret-internal-detail")

    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["request_id"]
    assert "super-secret-internal-detail" not in r.text
    assert "RuntimeError" not in r.text


def test_redaction_scrubs_tokens_and_sensitive_keys() -> None:
    raw = (
        "Header Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2ln "
        "and key csk_abc123_secretvalue"
    )
    cleaned = redact_text(raw)
    assert "csk_abc123_secretvalue" not in cleaned
    assert "eyJhbGciOiJIUzI1NiJ9" not in cleaned
    assert REDACTED in cleaned

    data = {"password": "pw", "nested": {"api_key": "k", "safe": "ok"}}
    scrubbed = scrub(data)
    assert scrubbed["password"] == REDACTED
    assert scrubbed["nested"]["api_key"] == REDACTED
    assert scrubbed["nested"]["safe"] == "ok"
