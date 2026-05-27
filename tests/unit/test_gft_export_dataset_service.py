from sqlalchemy import text

from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services.gft_export_dataset_service import build_gft_export_dataset


def test_export_dataset_works_without_atc_principal_codigo(db_session):
    db_session.add(GFTEstadoPresentacion(cn='999001', estado_gft='incluido', estado_editorial='publicado'))
    db_session.commit()
    db_session.execute(text('DROP VIEW IF EXISTS v_gft_publicada'))
    db_session.execute(text("""
        CREATE VIEW v_gft_publicada AS
        SELECT
          g.cn,
          g.nemonico,
          NULL::text AS nombre,
          NULL::text AS principio_activo,
          NULL::text AS codigo_atc_importado,
          NULL::text AS bifimed_sync_status,
          NULL::text AS cima_sync_status
        FROM gft_estado_presentacion g
        WHERE g.estado_gft='incluido' AND g.estado_editorial='publicado'
    """))
    db_session.commit()

    rows = build_gft_export_dataset(db_session)
    assert len(rows) == 1
    assert rows[0]['cn'] == '999001'
    assert rows[0]['codigo_atc'] is None
