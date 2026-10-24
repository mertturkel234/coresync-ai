from __future__ import annotations

import fakeredis
import pytest
import redis
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_live(client: TestClient) -> None:
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r.headers["x-request-id"]


def test_ready_reports_database_and_redis(client: TestClient) -> None:
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "ok"


def test_ready_without_redis_configured(settings: Settings) -> None:
    with TestClient(create_app(settings)) as c:
        body = c.get("/health/ready").json()
    assert body["checks"]["redis"]["status"] == "not_configured"
    assert body["status"] == "ok"


def test_ready_degraded_when_redis_down(settings: Settings) -> None:
    class DownRedis(fakeredis.FakeRedis):
        def ping(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise redis.ConnectionError("down")

    with TestClient(create_app(settings, redis_client=DownRedis())) as c:
        r = c.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["redis"]["status"] == "error"
    assert r.json()["checks"]["database"]["status"] == "ok"


def test_ready_degraded_when_database_unreachable(settings: Settings, tmp_path) -> None:
    # A directory cannot be opened as a SQLite database file, so connecting must fail.
    bad_dir = tmp_path / "isdir"
    bad_dir.mkdir()
    bad = settings.model_copy(update={"database_url": f"sqlite:///{bad_dir.as_posix()}"})
    with TestClient(create_app(bad)) as c:
        r = c.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["checks"]["database"]["status"] == "error"


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    r = client.get("/nope")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "not_found"
    assert err["request_id"] == r.headers["x-request-id"]


def test_client_request_id_is_echoed_only_when_well_formed(client: TestClient) -> None:
    good = client.get("/health/live", headers={"X-Request-ID": "abc12345-req"})
    assert good.headers["x-request-id"] == "abc12345-req"
    bad = client.get("/health/live", headers={"X-Request-ID": "x y\tz<script>"})
    assert bad.headers["x-request-id"] != "x y\tz<script>"


def test_production_requires_strong_jwt_secret() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            environment="production", database_url="postgresql://u:p@h/db", jwt_secret="change-me"
        )


def test_dev_generates_ephemeral_secret_when_unset() -> None:
    s = Settings(environment="development", jwt_secret=None)
    assert s.jwt_secret and len(s.jwt_secret) >= 32
