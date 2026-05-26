import contextlib
import io
import json
import pytest


def test_confirm_write_requires_limits(monkeypatch):
    from scripts import run_gft_cache_backfill as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    with pytest.raises(SystemExit):
        mod.main(['--confirm-write', '--scope', 'imported'])


def test_accepts_priority_and_seed_and_repair_flags(monkeypatch):
    from scripts import run_gft_cache_backfill as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    monkeypatch.setattr(mod, '_run_json', lambda *_: {})
    assert mod.main(['--dry-run', '--priority-mode', '--seed-from-imported-urls', '--repair-not-found-from-imported-url']) == 0


def test_rejects_candidate_mode_public_cli(monkeypatch):
    from scripts import run_gft_cache_backfill as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    with pytest.raises(SystemExit):
        mod.main(['--dry-run', '--candidate-mode', 'syncable'])


def test_imported_batch_safety_guard(monkeypatch):
    from scripts import run_gft_cache_backfill as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    with pytest.raises(SystemExit):
        mod.main(['--confirm-write', '--scope', 'imported', '--batch-size', '201', '--max-batches', '1'])


def test_dry_run_json_contains_before_phases_after_delta(monkeypatch, db_session):
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
    assert 'before' in out and 'phases' in out and 'after' in out and 'delta' in out


def test_fast_wrapper_delegates_to_cache_backfill(monkeypatch):
    from scripts import run_gft_fast_public_backfill as mod
    called = {}

    def fake_main(argv=None):
        called['argv'] = argv
        return 0

    monkeypatch.setattr(mod.cache_backfill, 'main', fake_main)
    assert mod.main(['--dry-run', '--batch-size', '3', '--max-batches', '2']) == 0
    assert '--scope' in called['argv'] and 'published' in called['argv']
