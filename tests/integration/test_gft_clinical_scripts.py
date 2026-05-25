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
    assert db_session.get(GftClinicalSummaryCache, '200001') is not None
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
