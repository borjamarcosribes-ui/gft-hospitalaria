from sqlalchemy import text

from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion


def _create_view(db_session):
    db_session.execute(text("DROP VIEW IF EXISTS v_gft_publicada"))
    db_session.execute(
        text(
            """
            CREATE VIEW v_gft_publicada AS
            SELECT g.cn
            FROM gft_estado_presentacion g
            WHERE g.estado_gft = 'incluido' AND g.estado_editorial = 'publicado'
            """
        )
    )
    db_session.commit()


def _seed_pub(db_session, cn: str):
    db_session.add(GFTEstadoPresentacion(cn=cn, estado_gft='incluido', estado_editorial='publicado'))


def test_sync_script_candidate_mode_syncable_and_confirm_write(monkeypatch, db_session):
    from scripts import sync_gft_clinical_sections as mod

    _seed_pub(db_session, '100001')
    _seed_pub(db_session, '100002')
    _seed_pub(db_session, '100003')
    _seed_pub(db_session, '100004')
    db_session.add(CimaMedicamentoCache(cn='100001', nregistro='NR1', sync_status='ok'))
    db_session.add(CimaMedicamentoCache(cn='100002', nregistro='NR2', sync_status='error'))
    db_session.add(CimaMedicamentoCache(cn='100003', nregistro='', sync_status='ok'))
    db_session.add(CimaFichaTecnicaCache(cn='100001', nregistro='NR1', tipo_documento=1, seccion='4.2', titulo='4.2', sync_status='ok', contenido_texto='x'))
    db_session.commit()
    _create_view(db_session)

    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)
    called = []

    def fake_sync(**kwargs):
        called.append((kwargs['cn'], kwargs['seccion']))

        class R:
            sync_status = 'ok'

        return R()

    monkeypatch.setattr(mod, 'sync_cima_segmented_section', fake_sync)

    rc = mod.main(['--dry-run', '--candidate-mode', 'syncable', '--sections', '4.2', '4.3', '--only-missing', '--limit', '10'])
    assert rc == 0
    assert called == []

    rc = mod.main(['--confirm-write', '--candidate-mode', 'syncable', '--sections', '4.2', '4.3', '--only-missing', '--limit', '10'])
    assert rc == 0
    assert ('100001', '4.3') in called
    assert ('100001', '4.2') not in called


def test_sync_script_confirm_write_requires_limit_or_cn(db_session):
    from scripts import sync_gft_clinical_sections as mod

    _seed_pub(db_session, '100010')
    db_session.commit()
    _create_view(db_session)
    try:
        mod.main(['--confirm-write'])
        assert False
    except SystemExit as exc:
        assert 'indique --limit o --cn' in str(exc)


def test_sync_script_only_missing_skips_existing_ok_with_html_content(monkeypatch, db_session):
    from scripts import sync_gft_clinical_sections as mod

    _seed_pub(db_session, '100020')
    db_session.add(CimaMedicamentoCache(cn='100020', nregistro='NR20', sync_status='ok'))
    db_session.add(
        CimaFichaTecnicaCache(
            cn='100020',
            nregistro='NR20',
            tipo_documento=1,
            seccion='4.2',
            titulo='4.2',
            sync_status='ok',
            contenido_texto='',
            contenido_html='<p>contenido existente</p>',
        )
    )
    db_session.commit()
    _create_view(db_session)
    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)
    called = []

    def fake_sync(**kwargs):
        called.append((kwargs['cn'], kwargs['seccion']))

        class R:
            sync_status = 'ok'

        return R()

    monkeypatch.setattr(mod, 'sync_cima_segmented_section', fake_sync)
    assert mod.main(['--confirm-write', '--candidate-mode', 'syncable', '--sections', '4.2', '--only-missing', '--limit', '10']) == 0
    assert called == []


def test_sync_script_only_missing_skips_when_duplicate_auditable_rows_exist(monkeypatch, db_session):
    from scripts import sync_gft_clinical_sections as mod
    import contextlib, io, json

    _seed_pub(db_session, '100021')
    db_session.add(CimaMedicamentoCache(cn='100021', nregistro='NR21', sync_status='ok'))
    db_session.add(CimaFichaTecnicaCache(cn='100021', nregistro='NR21A', tipo_documento=1, seccion='4.2', titulo='4.2', sync_status='ok', contenido_texto='texto A'))
    db_session.add(CimaFichaTecnicaCache(cn='100021', nregistro='NR21B', tipo_documento=1, seccion='4.2', titulo='4.2', sync_status='ok', contenido_html='<p>html B</p>'))
    db_session.commit()
    _create_view(db_session)
    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)
    called = []

    def fake_sync(**kwargs):
        called.append((kwargs['cn'], kwargs['seccion']))
        class R:
            sync_status = 'ok'
        return R()

    monkeypatch.setattr(mod, 'sync_cima_segmented_section', fake_sync)
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--confirm-write', '--candidate-mode', 'syncable', '--sections', '4.2', '--only-missing', '--limit', '10', '--json']) == 0
    out = json.loads(b.getvalue())
    assert called == []
    assert out['selected_candidates'] == 0
    assert out['processed_operations'] == 0
    assert out['skipped_existing_ok'] == 0
    assert out['remaining_syncable_candidates'] == 0
    assert out['by_status'].get('updated_existing_auditable', 0) == 0


def test_sync_script_duplicate_auditable_rows_count_is_cn_and_section_scoped(monkeypatch, db_session):
    from scripts import sync_gft_clinical_sections as mod
    import contextlib, io, json

    _seed_pub(db_session, '100022')
    db_session.add(CimaMedicamentoCache(cn='100022', nregistro='NR22', sync_status='ok'))
    db_session.add(CimaFichaTecnicaCache(cn='100022', nregistro='NR22A', tipo_documento=1, seccion='4.2', titulo='4.2', sync_status='ok', contenido_texto='texto A'))
    db_session.add(CimaFichaTecnicaCache(cn='100022', nregistro='NR22B', tipo_documento=1, seccion='4.2', titulo='4.2', sync_status='ok', contenido_html='<p>html B</p>'))
    db_session.add(CimaFichaTecnicaCache(cn='100022', nregistro='NR22C', tipo_documento=1, seccion='4.3', titulo='4.3', sync_status='ok', contenido_texto='texto C'))
    db_session.commit()
    _create_view(db_session)
    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)

    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--dry-run', '--candidate-mode', 'syncable', '--sections', '4.2', '--only-missing', '--limit', '10', '--json']) == 0
    out = json.loads(b.getvalue())
    assert out['selected_candidates'] == 0
    assert out['remaining_syncable_candidates'] == 0
    assert out['examples_remaining_syncable'] == []


def test_sync_script_counts_written_not_auditable_when_ok_without_content(monkeypatch, db_session):
    from scripts import sync_gft_clinical_sections as mod
    import contextlib, io, json

    _seed_pub(db_session, '100030')
    db_session.add(CimaMedicamentoCache(cn='100030', nregistro='NR30', sync_status='ok'))
    db_session.commit()
    _create_view(db_session)
    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)

    def fake_sync(**kwargs):
        row = CimaFichaTecnicaCache(
            cn=kwargs['cn'], nregistro=kwargs['nregistro'], tipo_documento=1, seccion=kwargs['seccion'], titulo=kwargs['seccion'], sync_status='ok', contenido_texto='', contenido_html=''
        )
        return row

    monkeypatch.setattr(mod, 'sync_cima_segmented_section', fake_sync)
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--confirm-write', '--candidate-mode', 'syncable', '--sections', '4.2', '--only-missing', '--limit', '10', '--json']) == 0
    out = json.loads(b.getvalue())
    assert out['by_status']['written_not_auditable'] == 1
    assert out['by_status'].get('written_new_auditable', 0) == 0


def test_sync_script_counts_written_not_auditable_when_ok_with_wrong_cn(monkeypatch, db_session):
    from scripts import sync_gft_clinical_sections as mod
    import contextlib, io, json

    _seed_pub(db_session, '100031')
    db_session.add(CimaMedicamentoCache(cn='100031', nregistro='NR31', sync_status='ok'))
    db_session.add(CimaFichaTecnicaCache(cn='999999', nregistro='NR31', tipo_documento=1, seccion='4.2', titulo='4.2', sync_status='ok', contenido_texto='texto'))
    db_session.commit()
    _create_view(db_session)
    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)

    def fake_sync(**kwargs):
        return db_session.query(CimaFichaTecnicaCache).filter(CimaFichaTecnicaCache.cn == '999999', CimaFichaTecnicaCache.seccion == '4.2').one()

    monkeypatch.setattr(mod, 'sync_cima_segmented_section', fake_sync)
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--confirm-write', '--candidate-mode', 'syncable', '--sections', '4.2', '--only-missing', '--limit', '10', '--json']) == 0
    out = json.loads(b.getvalue())
    assert out['by_status']['written_not_auditable'] == 1


def test_summary_script_uses_public_frontier_and_skips_not_public(monkeypatch, db_session):
    from scripts import generate_gft_clinical_summaries as mod

    _seed_pub(db_session, '200001')
    db_session.add(CimaMedicamentoCache(cn='200001', nregistro='NR200001', sync_status='ok'))
    db_session.add(CimaMedicamentoCache(cn='200999', nregistro='NR200999', sync_status='ok'))
    db_session.add(CimaFichaTecnicaCache(cn='200001', nregistro='NR200001', tipo_documento=1, seccion='4.1', titulo='4.1', sync_status='ok', contenido_texto='Indicaciones'))
    db_session.add(CimaFichaTecnicaCache(cn='200999', nregistro='NR200999', tipo_documento=1, seccion='4.1', titulo='4.1', sync_status='ok', contenido_texto='No público'))
    db_session.commit()
    _create_view(db_session)

    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)

    rc = mod.main(['--dry-run', '--candidate-mode', 'summary_ready', '--limit', '10'])
    assert rc == 0

    rc = mod.main(['--confirm-write', '--candidate-mode', 'summary_ready', '--limit', '10'])
    assert rc == 0
    row = db_session.get(GftClinicalSummaryCache, '200001')
    assert row is not None
    assert row.resumen_general is not None
    assert db_session.get(GftClinicalSummaryCache, '200999') is None

    rc = mod.main(['--confirm-write', '--cn', '200999'])
    assert rc == 0
    assert db_session.get(GftClinicalSummaryCache, '200999') is None


def test_summary_script_confirm_write_requires_limit_or_cn(db_session):
    from scripts import generate_gft_clinical_summaries as mod

    _seed_pub(db_session, '210001')
    db_session.commit()
    _create_view(db_session)
    try:
        mod.main(['--confirm-write'])
        assert False
    except SystemExit as exc:
        assert 'indique --limit o --cn' in str(exc)


def test_summary_missing_source_not_written_by_default_and_optional_write(monkeypatch, db_session):
    from scripts import generate_gft_clinical_summaries as mod

    _seed_pub(db_session, '220001')
    db_session.add(CimaMedicamentoCache(cn='220001', nregistro='NR220001', sync_status='ok'))
    db_session.commit()
    _create_view(db_session)
    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)

    rc = mod.main(['--confirm-write', '--cn', '220001'])
    assert rc == 0
    assert db_session.get(GftClinicalSummaryCache, '220001') is None

    rc = mod.main(['--confirm-write', '--cn', '220001', '--write-missing-source'])
    assert rc == 0
    row = db_session.get(GftClinicalSummaryCache, '220001')
    assert row is not None
    assert row.source_status == 'missing_source'


def test_summary_script_force_updates_resumen_general(monkeypatch, db_session):
    from scripts import generate_gft_clinical_summaries as mod

    _seed_pub(db_session, '230001')
    db_session.add(CimaMedicamentoCache(cn='230001', nregistro='NR230001', sync_status='ok'))
    db_session.add(CimaFichaTecnicaCache(cn='230001', nregistro='NR230001', tipo_documento=1, seccion='4.1', titulo='4.1', sync_status='ok', contenido_texto='Indicado para test clínico'))
    db_session.add(GftClinicalSummaryCache(cn='230001', source_status='ok', resumen_general='Antiguo resumen'))
    db_session.commit(); _create_view(db_session)
    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)

    assert mod.main(['--confirm-write', '--cn', '230001', '--force']) == 0
    row = db_session.get(GftClinicalSummaryCache, '230001')
    assert row is not None
    assert row.resumen_general is not None
    assert row.resumen_general != 'Antiguo resumen'


def test_summary_ready_only_missing_prioritizes_cn_without_summary(monkeypatch, db_session):
    from scripts import generate_gft_clinical_summaries as mod

    _seed_pub(db_session, '240001')
    _seed_pub(db_session, '240002')
    db_session.add(CimaMedicamentoCache(cn='240001', nregistro='NR240001', sync_status='ok'))
    db_session.add(CimaMedicamentoCache(cn='240002', nregistro='NR240002', sync_status='ok'))
    db_session.add(CimaFichaTecnicaCache(cn='240001', nregistro='NR240001', tipo_documento=1, seccion='4.1', titulo='4.1', sync_status='ok', contenido_texto='Texto A'))
    db_session.add(CimaFichaTecnicaCache(cn='240002', nregistro='NR240002', tipo_documento=1, seccion='4.1', titulo='4.1', sync_status='ok', contenido_texto='Texto B'))
    db_session.add(GftClinicalSummaryCache(cn='240001', source_status='ok', resumen_general='existente'))
    db_session.commit(); _create_view(db_session)
    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)

    assert mod.main(['--confirm-write', '--candidate-mode', 'summary_ready', '--only-missing', '--limit', '1']) == 0
    assert db_session.get(GftClinicalSummaryCache, '240002') is not None
