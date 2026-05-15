from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.services.cima_segmented_client import CimaSegmentedFetchResult


def _fake_segmented_ok(self, nregistro: str, tipo_documento: int = 1, seccion: str = "4.1"):
    return CimaSegmentedFetchResult(
        status="ok",
        data={
            "nregistro": nregistro,
            "tipo_documento": tipo_documento,
            "seccion": seccion,
            "titulo": "Indicaciones terapéuticas",
            "contenido_html": "<div><p>Texto HTML</p></div>",
            "contenido_texto": "Texto limpio",
        },
        raw_payload={"json": [{"seccion": seccion}], "text": "Texto limpio"},
    )


def test_cima_segmented_sync_endpoint_ok(client, monkeypatch, admin_headers):
    monkeypatch.setattr(
        "app.services.cima_segmented_client.CimaSegmentedClient.get_section_content",
        _fake_segmented_ok,
    )

    response = client.post("/cima/segmented/sync/70030?force=true", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["nregistro"] == "70030"
    assert body["tipo_documento"] == 1
    assert body["seccion"] == "4.1"
    assert body["sync_status"] == "ok"
    assert body["contenido_texto"] == "Texto limpio"


def test_cima_segmented_sync_endpoint_invalid_nregistro(client, admin_headers):
    response = client.post("/cima/segmented/sync/70030?seccion=", headers=admin_headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "seccion obligatoria"


def test_cima_segmented_cache_endpoint_ok(client, db_session, admin_headers):
    db_session.add(
        CimaFichaTecnicaCache(
            nregistro="70030",
            tipo_documento=1,
            seccion="4.1",
            cn="111111",
            titulo="Indicaciones terapéuticas",
            contenido_html="<p>Texto HTML</p>",
            contenido_texto="Texto limpio",
            raw_data={"json": [{"seccion": "4.1"}], "text": "Texto limpio"},
            sync_status="ok",
        )
    )
    db_session.commit()

    response = client.get("/cima/segmented/cache/70030?seccion=4.1", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["nregistro"] == "70030"
    assert body["tipo_documento"] == 1
    assert body["seccion"] == "4.1"
    assert body["cn"] == "111111"
    assert body["sync_status"] == "ok"
    assert body["contenido_texto"] == "Texto limpio"


def test_cima_segmented_cache_endpoint_404(client, admin_headers):
    response = client.get("/cima/segmented/cache/999999?seccion=4.1", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "CIMA segmented cache not found"


def test_cima_segmented_endpoint_does_not_expose_raw_data(client, monkeypatch, admin_headers):
    monkeypatch.setattr(
        "app.services.cima_segmented_client.CimaSegmentedClient.get_section_content",
        _fake_segmented_ok,
    )

    sync_response = client.post("/cima/segmented/sync/70030?force=true", headers=admin_headers)
    cache_response = client.get("/cima/segmented/cache/70030?seccion=4.1", headers=admin_headers)

    assert sync_response.status_code == 200
    assert cache_response.status_code == 200
    assert "raw_data" not in sync_response.json()
    assert "raw_data" not in cache_response.json()
