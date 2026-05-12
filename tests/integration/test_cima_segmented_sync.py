import pytest

from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.services.cima_segmented_client import CimaSegmentedFetchResult
from app.services.cima_segmented_sync_service import sync_cima_segmented_section


class FakeCimaSegmentedClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def get_section_content(self, nregistro: str, tipo_documento: int = 1, seccion: str = "4.1"):
        self.calls.append(
            {
                "nregistro": nregistro,
                "tipo_documento": tipo_documento,
                "seccion": seccion,
            }
        )
        return self.result


def _ok_result(contenido_texto="Texto limpio"):
    return CimaSegmentedFetchResult(
        status="ok",
        data={
            "nregistro": "70030",
            "tipo_documento": 1,
            "seccion": "4.1",
            "titulo": "Indicaciones terapéuticas",
            "contenido_html": "<div><p>Texto HTML</p></div>",
            "contenido_texto": contenido_texto,
        },
        raw_payload={"json": [{"seccion": "4.1"}], "text": contenido_texto},
    )


def _existing_cache_row(contenido_texto="Texto anterior", cn="111111"):
    return CimaFichaTecnicaCache(
        nregistro="70030",
        tipo_documento=1,
        seccion="4.1",
        cn=cn,
        titulo="Indicaciones terapéuticas",
        contenido_html="<p>Texto anterior</p>",
        contenido_texto=contenido_texto,
        raw_data={"json": [{"seccion": "4.1"}], "text": contenido_texto},
        sync_status="ok",
    )


def test_sync_cima_segmented_section_ok_creates_cache_row(db_session):
    fake_client = FakeCimaSegmentedClient(_ok_result())

    row = sync_cima_segmented_section(db_session, "70030", cn="111111", client=fake_client)

    assert row.sync_status == "ok"
    assert row.sync_error is None
    assert row.cn == "111111"
    assert row.contenido_texto == "Texto limpio"
    assert row.raw_data == {"json": [{"seccion": "4.1"}], "text": "Texto limpio"}
    assert row.last_synced_at is not None
    assert fake_client.calls == [
        {"nregistro": "70030", "tipo_documento": 1, "seccion": "4.1"}
    ]


def test_sync_cima_segmented_section_reuses_cache_when_not_forced(db_session):
    existing = _existing_cache_row()
    db_session.add(existing)
    db_session.commit()
    fake_client = FakeCimaSegmentedClient(_ok_result(contenido_texto="Texto nuevo"))

    row = sync_cima_segmented_section(
        db_session,
        "70030",
        force=False,
        client=fake_client,
    )

    assert row.id == existing.id
    assert row.contenido_texto == "Texto anterior"
    assert fake_client.calls == []


def test_sync_cima_segmented_section_force_refreshes_existing_row(db_session):
    existing = _existing_cache_row(contenido_texto="Texto antiguo")
    db_session.add(existing)
    db_session.commit()
    fake_client = FakeCimaSegmentedClient(_ok_result(contenido_texto="Texto nuevo"))

    row = sync_cima_segmented_section(
        db_session,
        "70030",
        force=True,
        client=fake_client,
    )

    assert row.id == existing.id
    assert row.sync_status == "ok"
    assert row.contenido_texto == "Texto nuevo"
    assert fake_client.calls == [
        {"nregistro": "70030", "tipo_documento": 1, "seccion": "4.1"}
    ]


def test_sync_cima_segmented_section_not_found_preserves_existing_content(db_session):
    existing = _existing_cache_row(contenido_texto="Texto anterior")
    db_session.add(existing)
    db_session.commit()
    fake_client = FakeCimaSegmentedClient(
        CimaSegmentedFetchResult(
            status="not_found",
            error="No encontrado",
            raw_payload={"json": {"error": "x"}},
        )
    )

    row = sync_cima_segmented_section(
        db_session,
        "70030",
        force=True,
        client=fake_client,
    )

    assert row.sync_status == "not_found"
    assert row.sync_error == "No encontrado"
    assert row.contenido_texto == "Texto anterior"


def test_sync_cima_segmented_section_section_unavailable_preserves_existing_content(db_session):
    existing = _existing_cache_row(contenido_texto="Texto anterior")
    db_session.add(existing)
    db_session.commit()
    fake_client = FakeCimaSegmentedClient(
        CimaSegmentedFetchResult(
            status="section_unavailable",
            error="Sección no disponible",
            raw_payload={"json": {"error": "x"}},
        )
    )

    row = sync_cima_segmented_section(
        db_session,
        "70030",
        force=True,
        client=fake_client,
    )

    assert row.sync_status == "section_unavailable"
    assert row.sync_error == "Sección no disponible"
    assert row.contenido_texto == "Texto anterior"


def test_sync_cima_segmented_section_error_preserves_existing_content(db_session):
    existing = _existing_cache_row(contenido_texto="Texto anterior")
    db_session.add(existing)
    db_session.commit()
    fake_client = FakeCimaSegmentedClient(
        CimaSegmentedFetchResult(
            status="error",
            error="timeout",
            raw_payload={"json": {"error": "x"}},
        )
    )

    row = sync_cima_segmented_section(
        db_session,
        "70030",
        force=True,
        client=fake_client,
    )

    assert row.sync_status == "error"
    assert row.sync_error == "timeout"
    assert row.contenido_texto == "Texto anterior"


def test_sync_cima_segmented_section_identity_does_not_use_cn(db_session):
    first_client = FakeCimaSegmentedClient(_ok_result())
    first_row = sync_cima_segmented_section(
        db_session,
        "70030",
        cn="111111",
        client=first_client,
    )
    second_client = FakeCimaSegmentedClient(_ok_result(contenido_texto="Texto nuevo"))

    second_row = sync_cima_segmented_section(
        db_session,
        "70030",
        cn="222222",
        force=False,
        client=second_client,
    )

    row_count = (
        db_session.query(CimaFichaTecnicaCache)
        .filter_by(nregistro="70030", tipo_documento=1, seccion="4.1")
        .count()
    )
    assert row_count == 1
    assert second_row.id == first_row.id
    assert second_row.cn == "111111"
    assert second_client.calls == []


def test_sync_cima_segmented_section_validates_required_nregistro_and_seccion(db_session):
    with pytest.raises(ValueError, match="nregistro obligatorio"):
        sync_cima_segmented_section(db_session, "")

    with pytest.raises(ValueError, match="seccion obligatoria"):
        sync_cima_segmented_section(db_session, "70030", seccion="")
