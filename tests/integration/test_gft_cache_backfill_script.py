import contextlib
import io
import json
import pytest


def test_confirm_write_requires_limits(monkeypatch):
    from scripts import run_gft_cache_backfill as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    with pytest.raises(SystemExit):
        mod.main(['--confirm-write', '--scope', 'imported'])


def test_dry_run_json_contains_delta(monkeypatch, db_session):
    from scripts import run_gft_cache_backfill as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    monkeypatch.setattr(mod.audit, 'ensure_postgresql_database', lambda *_: None)
    monkeypatch.setattr(mod.linkage, 'ensure_postgresql_database', lambda *_: None)
    monkeypatch.setattr(mod.audit, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(mod.linkage.a, 'SessionLocal', lambda: db_session)

    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--dry-run', '--scope', 'published', '--batch-size', '1', '--max-batches', '1', '--json', '--allow-default-db']) == 0
    out = json.loads(b.getvalue())
    assert 'delta' in out
