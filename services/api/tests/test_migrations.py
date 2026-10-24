from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _alembic_cfg(db_url: str) -> Config:
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_alembic_upgrade_and_downgrade_on_fresh_database(tmp_path: Path) -> None:
    db_url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    cfg = _alembic_cfg(db_url)

    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    tables = set(inspect(engine).get_table_names())
    expected = {
        "users",
        "tenants",
        "memberships",
        "projects",
        "documents",
        "endpoints",
        "doc_chunks",
        "integration_sessions",
        "messages",
        "code_examples",
        "sandbox_credentials",
        "test_runs",
        "audit_events",
    }
    assert expected.issubset(tables)

    command.check(cfg)

    command.downgrade(cfg, "base")
    engine.dispose()
    engine2 = create_engine(db_url)
    remaining = set(inspect(engine2).get_table_names()) - {"alembic_version"}
    assert remaining == set()
    engine2.dispose()
