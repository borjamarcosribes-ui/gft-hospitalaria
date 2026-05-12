import pytest

from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache


def test_cima_segmented_cache_persists_json_status_and_unique_identity(db_session):
    raw_data = {"json": [{"seccion": "4.1"}], "text": "Texto de indicaciones"}
    cache_entry = CimaFichaTecnicaCache(
        nregistro="70030",
        tipo_documento=1,
        seccion="4.1",
        titulo="Indicaciones terapéuticas",
        contenido_texto="Texto de indicaciones",
        raw_data=raw_data,
        sync_status="ok",
    )

    db_session.add(cache_entry)
    db_session.commit()

    stored_entry = db_session.query(CimaFichaTecnicaCache).filter_by(
        nregistro="70030",
        tipo_documento=1,
        seccion="4.1",
    ).one()

    assert stored_entry.sync_status == "ok"
    assert stored_entry.raw_data == raw_data
    assert stored_entry.cn is None

    duplicate_entry = CimaFichaTecnicaCache(
        nregistro="70030",
        tipo_documento=1,
        seccion="4.1",
        titulo="Indicaciones terapéuticas duplicadas",
    )
    db_session.add(duplicate_entry)

    with pytest.raises(Exception):
        db_session.commit()

    db_session.rollback()
