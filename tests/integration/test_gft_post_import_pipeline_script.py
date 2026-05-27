import contextlib
import io
import json
import pytest


def test_documented_dry_run_command_does_not_raise_argparse(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    monkeypatch.setattr(mod, '_run_json', lambda *_: {})
    assert mod.main([
        '--dry-run', '--scope', 'published', '--priority-mode', '--batch-size', '50', '--max-batches', '1',
        '--bifimed-limit', '50', '--cima-med-limit', '50', '--sections-limit', '25', '--summaries-limit', '50',
        '--sections', '4.1', '4.2', '4.3', '4.4', '4.6', '--only-missing', '--seed-from-imported-urls',
        '--repair-not-found-from-imported-url', '--workers', '1', '--json'
    ]) == 0


def test_workers_gt_1_aborts_with_clear_message(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    with pytest.raises(SystemExit, match='workers > 1 todavía no implementado'):
        mod.main(['--dry-run', '--workers', '2'])


def test_phase_limit_and_flags_propagation(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)

    captured = {}

    def fake_run(fn, argv):
        captured.setdefault(fn.__module__.split('.')[-1], []).append(list(argv))
        if 'coverage' in fn.__module__:
            return {'bifimed': {'con_cache': 0, 'sync_status_counts': {'ok': 0}}, 'cima': {'con_cache': 0, 'ok': 0}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 0}}}
        return {}

    monkeypatch.setattr(mod, '_run_json', fake_run)

    mod.main([
        '--dry-run', '--scope', 'published', '--bifimed-limit', '11', '--cima-med-limit', '12', '--sections-limit', '13', '--summaries-limit', '14',
        '--seed-from-imported-urls', '--repair-not-found-from-imported-url', '--refresh-bifimed-ok', '--retry-bifimed-not-found', '--sections', '4.1'
    ])

    bif = ' '.join(captured['run_gft_bifimed_backfill'][0])
    cima = ' '.join(captured['run_gft_cima_medicamento_backfill'][0])
    sec = ' '.join(captured['sync_gft_clinical_sections'][0])
    summ = ' '.join(captured['generate_gft_clinical_summaries'][0])

    assert '--batch-size 11' in bif and '--refresh-ok' in bif and '--retry-not-found' in bif
    assert '--batch-size 12' in cima and '--seed-from-imported-urls' in cima and '--repair-not-found-from-imported-url' in cima
    assert '--limit 13' in sec and '--candidate-mode syncable' in sec
    assert '--limit 14' in summ and '--candidate-mode summary_ready' in summ


def test_skip_flags_skip_phases(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)

    called = []
    def fake_run(fn, argv):
        called.append(fn.__module__.split('.')[-1])
        if 'coverage' in fn.__module__:
            return {'bifimed': {'con_cache': 0, 'sync_status_counts': {'ok': 0}}, 'cima': {'con_cache': 0, 'ok': 0}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 0}}}
        return {}
    monkeypatch.setattr(mod, '_run_json', fake_run)

    mod.main(['--dry-run', '--skip-bifimed', '--skip-cima-med', '--skip-cima-sections', '--skip-summaries', '--sections', '4.1'])
    assert called.count('gft_linkage_coverage_audit') == 2
    assert 'run_gft_bifimed_backfill' not in called
    assert 'run_gft_cima_medicamento_backfill' not in called


def test_output_has_required_json_shape(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)

    calls = [
        {'bifimed': {'con_cache': 1, 'sync_status_counts': {'ok': 1}}, 'cima': {'con_cache': 1, 'ok': 1}, 'summaries': {'con_resumen': 1, 'con_resumen_general': 1}, 'completion': {'clinical_ready': 1, 'fully_linked_public_detail_ready': 1}, 'sections': {'coverage_by_section': {'4.1': 1}}},
        {'processed': 1, 'by_status': {}}, {'processed': 1, 'by_status': {}}, {'processed_operations': 1, 'by_status': {}}, {'processed': 1, 'by_source_status': {}},
        {'bifimed': {'con_cache': 2, 'sync_status_counts': {'ok': 2}}, 'cima': {'con_cache': 2, 'ok': 2}, 'summaries': {'con_resumen': 2, 'con_resumen_general': 2}, 'completion': {'clinical_ready': 2, 'fully_linked_public_detail_ready': 2}, 'sections': {'coverage_by_section': {'4.1': 2}}},
    ]
    monkeypatch.setattr(mod, '_run_json', lambda *_: calls.pop(0))

    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--dry-run', '--sections', '4.1', '--json']) == 0
    out = json.loads(b.getvalue())
    for k in ['before', 'phases', 'after', 'delta', 'performance', 'runtime_log_path']:
        assert k in out


def test_clinical_warning_when_sections_ok_but_zero_delta(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    calls = [
        {'bifimed': {'con_cache': 1, 'sync_status_counts': {'ok': 1}}, 'cima': {'con_cache': 1, 'ok': 1}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 1}, 'examples_missing_sections': ['111111'], 'post_sections_status_counts': {'4.1': {'ok': 1}}}},
        {'processed': 1, 'by_status': {}}, {'processed': 1, 'by_status': {}}, {'processed_operations': 1, 'by_status': {'written_new_auditable': 5}}, {'processed': 1, 'by_source_status': {}},
        {'bifimed': {'con_cache': 2, 'sync_status_counts': {'ok': 2}}, 'cima': {'con_cache': 2, 'ok': 2}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 1}, 'examples_missing_sections': ['111111'], 'post_sections_status_counts': {'4.1': {'ok': 2, 'section_unavailable': 1}}}},
    ]
    monkeypatch.setattr(mod, '_run_json', lambda *_: calls.pop(0))
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--dry-run', '--sections', '4.1', '--json']) == 0
    out = json.loads(b.getvalue())
    assert out['clinical_phase_warning']['code'] == 'sections_ok_but_zero_delta'
    assert out['post_sections_status_counts']['4.1']['ok'] == 2
    assert out['examples_sections_written_not_counted'] == ['111111']


def test_no_clinical_warning_when_only_skipped_existing_ok(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    calls = [
        {'bifimed': {'con_cache': 1, 'sync_status_counts': {'ok': 1}}, 'cima': {'con_cache': 1, 'ok': 1}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 1}, 'examples_missing_sections': [], 'post_sections_status_counts': {'4.1': {'ok': 1}}}},
        {'processed': 1, 'by_status': {}}, {'processed': 1, 'by_status': {}}, {'processed_operations': 0, 'by_status': {'skipped_existing_ok': 5}}, {'processed': 1, 'by_source_status': {}},
        {'bifimed': {'con_cache': 1, 'sync_status_counts': {'ok': 1}}, 'cima': {'con_cache': 1, 'ok': 1}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 1}, 'examples_missing_sections': [], 'post_sections_status_counts': {'4.1': {'ok': 1}}}},
    ]
    monkeypatch.setattr(mod, '_run_json', lambda *_: calls.pop(0))
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--dry-run', '--sections', '4.1', '--json']) == 0
    out = json.loads(b.getvalue())
    assert out['clinical_phase_warning'] is None


def test_pipeline_warns_sections_written_not_auditable(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    calls = [
        {'bifimed': {'con_cache': 1, 'sync_status_counts': {'ok': 1}}, 'cima': {'con_cache': 1, 'ok': 1}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 1}, 'examples_missing_sections': ['111111'], 'post_sections_status_counts': {'4.1': {'ok': 1}}}},
        {'processed_operations': 1, 'by_status': {'written_not_auditable': 1}, 'examples_written_not_auditable': [{'cn': '602914', 'section': '4.1'}]},
        {'bifimed': {'con_cache': 1, 'sync_status_counts': {'ok': 1}}, 'cima': {'con_cache': 1, 'ok': 1}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 1}, 'examples_missing_sections': ['111111'], 'post_sections_status_counts': {'4.1': {'ok': 1}}}},
    ]
    monkeypatch.setattr(mod, '_run_json', lambda *_: calls.pop(0))
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--dry-run', '--sections', '4.1', '--skip-bifimed', '--skip-cima-med', '--skip-summaries', '--json']) == 0
    out = json.loads(b.getvalue())
    assert out['clinical_phase_warning']['code'] == 'sections_written_not_auditable'
    assert out['examples_sections_written_not_counted'][0]['cn'] == '602914'


def test_pipeline_no_warning_when_only_skipped_and_duplicate_diagnostics(monkeypatch):
    from scripts import run_gft_post_import_pipeline as mod
    monkeypatch.setattr(mod, 'ensure_postgresql_database', lambda *_: None)
    calls = [
        {'bifimed': {'con_cache': 1, 'sync_status_counts': {'ok': 1}}, 'cima': {'con_cache': 1, 'ok': 1}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 1}, 'examples_missing_sections': [], 'post_sections_status_counts': {'4.1': {'ok': 2}}}},
        {'processed_operations': 0, 'by_status': {'skipped_existing_ok': 10, 'duplicate_auditable_rows': 10}},
        {'bifimed': {'con_cache': 1, 'sync_status_counts': {'ok': 1}}, 'cima': {'con_cache': 1, 'ok': 1}, 'summaries': {'con_resumen': 0, 'con_resumen_general': 0}, 'completion': {'clinical_ready': 0, 'fully_linked_public_detail_ready': 0}, 'sections': {'coverage_by_section': {'4.1': 1}, 'examples_missing_sections': [], 'post_sections_status_counts': {'4.1': {'ok': 2}}}},
    ]
    monkeypatch.setattr(mod, '_run_json', lambda *_: calls.pop(0))
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--dry-run', '--sections', '4.1', '--skip-bifimed', '--skip-cima-med', '--skip-summaries', '--json']) == 0
    out = json.loads(b.getvalue())
    assert out['clinical_phase_warning'] is None
