import pytest

from scripts._db_guard import ensure_postgresql_database


def test_db_guard_aborts_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="DATABASE_URL no apunta a PostgreSQL"):
        ensure_postgresql_database()


def test_db_guard_aborts_with_sqlite_without_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    with pytest.raises(SystemExit, match="DATABASE_URL no apunta a PostgreSQL"):
        ensure_postgresql_database()


def test_db_guard_allows_sqlite_with_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    ensure_postgresql_database(allow_default_db=True)


def test_db_guard_allows_postgresql(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://gft:gft@localhost:5432/gft")
    ensure_postgresql_database()
