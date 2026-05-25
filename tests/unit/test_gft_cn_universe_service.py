from sqlalchemy import text
from app.services.gft_cn_universe_service import get_cn_universe


def _seed(db):
    db.execute(text("INSERT INTO gft_estado_presentacion (cn, estado_gft) VALUES ('0001','incluido'),('2','excluido')"))
    db.execute(text("INSERT INTO import_row_staging (id,batch_id,row_number,cn_normalized,estado_gft,validation_errors,validation_warnings,raw_payload,created_at) VALUES (gen_random_uuid(), gen_random_uuid(),1,'0003','incluido','[]'::json,'[]'::json,'{}'::json,now()), (gen_random_uuid(), gen_random_uuid(),2,' 0004 ','incluido','[]'::json,'[]'::json,'{}'::json,now())"))
    db.execute(text("INSERT INTO cima_medicamento_cache (cn,sync_status) VALUES ('0005','ok')"))
    db.execute(text("INSERT INTO bifimed_cache (cn,sync_status) VALUES ('0006','ok')"))
    db.execute(text("CREATE OR REPLACE VIEW v_gft_publicada AS SELECT '0001'::text AS cn"))
    db.commit()


def test_scopes(db_session):
    _seed(db_session)
    assert get_cn_universe(db_session, 'published') == ['0001']
    assert get_cn_universe(db_session, 'included') == ['0001']
    assert get_cn_universe(db_session, 'state') == ['0001', '2']
    assert get_cn_universe(db_session, 'imported') == ['0003', '0004']
    all_known = get_cn_universe(db_session, 'all_known')
    assert '0001' in all_known and '0006' in all_known


def test_explicit_keeps_zeroes(db_session):
    assert get_cn_universe(db_session, 'published', [' 0007 ', '0007']) == ['0007']
