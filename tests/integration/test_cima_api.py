class FakeOk:
    status = "ok"
    error = None
    raw_payload = {"x": 1}
    data = {
        "nregistro": "nr",
        "nombre": "N",
        "presentacion": "P",
        "forma_farmaceutica": "F",
        "forma_farmaceutica_simplificada": "FS",
        "vias_administracion_json": [],
        "atc_json": [],
        "principios_activos_json": [],
        "documentos_json": [{"tipo": 1, "url": "u1"}, {"tipo": 2, "url": "u2"}],
        "url_ficha_tecnica": "u1",
        "url_prospecto": "u2",
        "fecha_ficha_tecnica": None,
        "fecha_prospecto": None,
    }


def test_cima_sync_and_get_cache(client, monkeypatch):
    monkeypatch.setattr('app.services.cima_sync_service.CimaClient.get_by_cn', lambda self, cn: FakeOk())
    r = client.post('/cima/sync/123456?force=true')
    assert r.status_code == 200
    body = r.json()
    assert body["sync_status"] == "ok"
    assert body["url_ficha_tecnica"] == "u1"
    assert body["url_prospecto"] == "u2"

    r2 = client.get('/cima/cache/123456')
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["url_ficha_tecnica"] == "u1"
    assert body2["url_prospecto"] == "u2"
