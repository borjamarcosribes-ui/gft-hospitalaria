import contextlib
import io
import json
import pytest


def test_cli_accepts_workers_and_phase_limits(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    monkeypatch.setattr(mod, '_run_json', lambda *_: {})
    assert mod.main([
        '--dry-run', '--workers', '3', '--bifimed-limit', '10', '--cima-med-limit', '10', '--sections-limit', '10', '--summaries-limit', '10'
    ]) == 0


def test_confirm_write_requires_phase_limits(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    with pytest.raises(SystemExit):
        mod.main(['--confirm-write', '--batch-size', '10', '--max-batches', '1'])


def test_imported_batch_guard(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    with pytest.raises(SystemExit):
        mod.main(['--dry-run', '--scope', 'imported', '--batch-size', '201'])


def test_output_has_performance_delta_and_log(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)

    calls = [
        {'bifimed': {'con_cache': 1, 'sync_status_counts': {'ok': 1}}, 'cima': {'con_cache': 1, 'ok': 1}, 'summaries': {'con_resumen': 1, 'con_resumen_general': 1}, 'completion': {'clinical_ready': 1, 'fully_linked_public_detail_ready': 1}, 'sections': {'coverage_by_section': {'4.1': 1}}},
        {'bifimed': {'processed': 1, 'by_status': {}}, 'cima_medicamento': {'processed': 1, 'by_status': {}}},
        {'bifimed': {'con_cache': 2, 'sync_status_counts': {'ok': 2}}, 'cima': {'con_cache': 2, 'ok': 2}, 'summaries': {'con_resumen': 2, 'con_resumen_general': 2}, 'completion': {'clinical_ready': 2, 'fully_linked_public_detail_ready': 2}, 'sections': {'coverage_by_section': {'4.1': 2}}},
    ]
    monkeypatch.setattr(mod, '_run_json', lambda *_: calls.pop(0))

    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--dry-run', '--sections', '4.1', '--json']) == 0
    out = json.loads(b.getvalue())
    assert 'performance' in out and 'delta' in out and 'runtime_log_path' in out
