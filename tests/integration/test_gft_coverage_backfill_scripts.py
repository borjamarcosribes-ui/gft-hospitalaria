from sqlalchemy import text
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.bifimed_cache import BifimedCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache

def _create_view(db_session):
    db_session.execute(text('DROP VIEW IF EXISTS v_gft_publicada'))
    db_session.execute(text("""CREATE VIEW v_gft_publicada AS SELECT cn FROM gft_estado_presentacion WHERE estado_gft='incluido' AND estado_editorial='publicado'"""))
    db_session.commit()

def test_audits_and_backfill_dry_run(monkeypatch, db_session):
    from scripts import gft_clinical_coverage_audit as ca, gft_bifimed_coverage_audit as ba, run_gft_clinical_backfill as bf
    db_session.add(GFTEstadoPresentacion(cn='300001', estado_gft='incluido', estado_editorial='publicado'))
    db_session.add(GFTEstadoPresentacion(cn='300002', estado_gft='incluido', estado_editorial='publicado'))
    db_session.add(CimaMedicamentoCache(cn='300001', nregistro='NR1', sync_status='ok'))
    db_session.add(CimaFichaTecnicaCache(cn='300001', nregistro='NR1', seccion='4.2', tipo_documento=1, titulo='4.2', sync_status='ok', contenido_texto='insuficiencia renal'))
    db_session.add(BifimedCache(cn='300001', situacion_financiacion='Sí', condiciones_financiacion_restringidas='Restricción test', condiciones_especiales_financiacion=None))
    db_session.commit(); _create_view(db_session)
    monkeypatch.setattr(ca, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(ba, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(bf.audit_mod, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(bf.sync_mod, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(bf.sum_mod, 'SessionLocal', lambda: db_session)
    assert ca.main(['--json']) == 0
    assert ba.main(['--json']) == 0
    assert bf.main(['--dry-run','--batch-size','1','--max-batches','1','--json']) == 0


def test_linkage_audit_excludes_missing_source_from_useful_counts(monkeypatch, db_session):
    from scripts import gft_linkage_coverage_audit as mod

    db_session.add(GFTEstadoPresentacion(cn='310001', estado_gft='incluido', estado_editorial='publicado'))
    db_session.add(GFTEstadoPresentacion(cn='310002', estado_gft='incluido', estado_editorial='publicado'))
    db_session.add(GftClinicalSummaryCache(cn='310001', source_status='missing_source', resumen_ajuste_renal='No localizado automáticamente', resumen_ajuste_hepatico='No informado'))
    db_session.add(GftClinicalSummaryCache(cn='310002', source_status='ok', resumen_general='Resumen útil', resumen_ajuste_renal='Ajustar por FG', resumen_ajuste_hepatico='Sin ajuste', resumen_embarazo='Evitar', resumen_lactancia='Precaución'))
    db_session.commit(); _create_view(db_session)

    monkeypatch.setattr(mod, 'SessionLocal', lambda: db_session)
    import io, contextlib, json
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--scope', 'published', '--json']) == 0
    out = json.loads(b.getvalue())
    assert out['summaries']['con_resumen'] == 1
    assert out['summaries']['con_resumen_general'] == 1
    assert out['summaries']['con_ajuste_renal'] == 1
    assert out['summaries']['con_ajuste_hepatico'] == 1
    assert out['summaries']['con_embarazo'] == 1
    assert out['summaries']['con_lactancia'] == 1


def test_linkage_backfill_skips_summaries_for_cima_not_found(monkeypatch, db_session):
    from scripts import run_gft_linkage_backfill as mod

    db_session.add(GFTEstadoPresentacion(cn='320001', estado_gft='incluido', estado_editorial='publicado'))
    db_session.add(CimaMedicamentoCache(cn='320001', nregistro='', sync_status='not_found'))
    db_session.commit(); _create_view(db_session)
    monkeypatch.setattr(mod.a, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(mod.cl.audit_mod, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(mod.cl.sync_mod, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(mod.cl.sum_mod, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(mod.c, 'SessionLocal', lambda: db_session)
    monkeypatch.setattr(mod.b, 'SessionLocal', lambda: db_session)

    import io, contextlib, json
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        assert mod.main(['--confirm-write', '--scope', 'published', '--cn', '320001', '--only-missing', '--json']) == 0
    out = json.loads(b.getvalue())
    assert out['clinical']['batches'][0]['summaries']['written'] == 0
    assert db_session.get(GftClinicalSummaryCache, '320001') is None
