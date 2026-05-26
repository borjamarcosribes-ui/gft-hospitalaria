from sqlalchemy import text
from app.services.gft_cn_universe_service import get_cn_universe


def _seed(db):
    db.execute(text("INSERT INTO gft_estado_presentacion (cn, estado_gft, estado_editorial, updated_at) VALUES ('0001','incluido','publicado','2026-01-01 00:00:00'),('2','excluido','borrador','2026-01-01 00:00:00'),('0008','pendiente_revision','borrador','2026-01-01 00:00:00')"))
    db.execute(text("INSERT INTO import_row_staging (id,batch_id,row_number,cn_normalized,estado_gft,validation_errors,validation_warnings,raw_payload,created_at) VALUES ('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000011',1,'0003','incluido','[]','[]','{}',CURRENT_TIMESTAMP), ('00000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000012',2,' 0004 ','incluido','[]','[]','{}',CURRENT_TIMESTAMP), ('00000000-0000-0000-0000-000000000003','00000000-0000-0000-0000-000000000013',3,'0008','pendiente_revision','[]','[]','{}',CURRENT_TIMESTAMP)"))
    db.execute(text("INSERT INTO cima_medicamento_cache (cn,sync_status) VALUES ('0005','ok')"))
    db.execute(text("INSERT INTO bifimed_cache (cn,sync_status) VALUES ('0006','ok')"))
    db.execute(text("DROP VIEW IF EXISTS v_gft_publicada"))
    db.execute(text("CREATE VIEW v_gft_publicada AS SELECT '0001' AS cn"))
    db.commit()


def test_scopes(db_session):
    _seed(db_session)
    assert get_cn_universe(db_session, 'published') == ['0001']
    assert get_cn_universe(db_session, 'included') == ['0001']
    assert get_cn_universe(db_session, 'pending') == ['0008']
    assert get_cn_universe(db_session, 'imported') == ['0003', '0004', '0008']
    all_known = get_cn_universe(db_session, 'all_known')
    assert '0001' in all_known and '0006' in all_known and '0008' in all_known


def test_explicit_keeps_zeroes(db_session):
    assert get_cn_universe(db_session, 'published', [' 0007 ', '0007']) == ['0007']
