"""Shared pytest fixtures.

Tests run on a file-backed SQLite database per test (PostgreSQL is not available in the default
development environment; see docs/DEVELOPMENT.md) and an in-memory fake Redis.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import fakeredis
import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        storage_dir=str(tmp_path / "storage"),
        redis_url=None,
        jwt_secret="test-secret-test-secret-test-secret-123456",
        cors_origins="http://localhost:3000",
    )


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis()


@pytest.fixture
def client(settings: Settings, fake_redis: fakeredis.FakeRedis) -> Iterator[TestClient]:
    app = create_app(settings, redis_client=fake_redis)
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as c:
        yield c
