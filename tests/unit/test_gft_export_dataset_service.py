from sqlalchemy import text

from app.models.bifimed_cache import BifimedCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services.gft_export_dataset_service import build_gft_export_dataset


def test_export_dataset_enriches_readiness_without_view_readiness_columns(db_session):
    cn = '999001'
    db_session.add(GFTEstadoPresentacion(cn=cn, estado_gft='incluido', estado_editorial='publicado', nemonico='N1'))
    db_session.add(BifimedCache(cn=cn, sync_status='ok'))
    db_session.add(CimaMedicamentoCache(cn=cn, nregistro='NR999', sync_status='ok'))
    for sec in ['4.1', '4.2', '4.3', '4.4', '4.6']:
        db_session.add(CimaFichaTecnicaCache(cn=cn, nregistro='NR999', tipo_documento=1, seccion=sec, titulo=sec, sync_status='ok', contenido_texto='texto'))
    db_session.add(GftClinicalSummaryCache(cn=cn, source_status='ok', resumen_general='r'))
    db_session.commit()

    db_session.execute(text('DROP VIEW IF EXISTS v_gft_publicada'))
    db_session.execute(text("""
        CREATE VIEW v_gft_publicada AS
        SELECT g.cn, CAST(NULL AS TEXT) AS nombre, CAST(NULL AS TEXT) AS principio_activo, CAST(NULL AS TEXT) AS codigo_atc_importado
        FROM gft_estado_presentacion g
        WHERE g.estado_gft='incluido' AND g.estado_editorial='publicado'
    """))
    db_session.commit()

    rows = build_gft_export_dataset(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row['bifimed_ok'] is True
    assert row['cima_ok'] is True
    assert row['sections_complete'] is True
    assert row['summary_ok'] is True
    assert row['fully_linked_public_detail_ready'] is True
