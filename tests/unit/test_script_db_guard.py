import pytest

from scripts import gft_linkage_coverage_audit


def test_gft_linkage_coverage_audit_aborts_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="DATABASE_URL no apunta a PostgreSQL"):
        gft_linkage_coverage_audit.main(["--scope", "published", "--json"])


def test_gft_linkage_coverage_audit_aborts_with_sqlite_without_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    with pytest.raises(SystemExit, match="DATABASE_URL no apunta a PostgreSQL"):
        gft_linkage_coverage_audit.main(["--scope", "published", "--json"])


def test_gft_linkage_coverage_audit_allows_sqlite_with_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    with pytest.raises(Exception):
        gft_linkage_coverage_audit.main(["--scope", "published", "--json", "--allow-default-db"])
