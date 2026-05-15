import uuid

from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging


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


def test_cima_sync_and_get_cache(client, monkeypatch, admin_headers):
    monkeypatch.setattr(
        "app.services.cima_sync_service.CimaClient.get_by_cn",
        lambda self, cn: FakeOk(),
    )

    r = client.post("/cima/sync/123456?force=true", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["sync_status"] == "ok"
    assert body["url_ficha_tecnica"] == "u1"
    assert body["url_prospecto"] == "u2"

    r2 = client.get("/cima/cache/123456", headers=admin_headers)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["url_ficha_tecnica"] == "u1"
    assert body2["url_prospecto"] == "u2"


def test_cima_sync_import_batch_endpoint(client, db_session, monkeypatch, admin_headers):
    batch = ImportBatch(filename="x.xlsx", status="validated")
    db_session.add(batch)
    db_session.flush()

    db_session.add(
        ImportRowStaging(
            id=uuid.uuid4(),
            batch_id=batch.id,
            row_number=1,
            cn_normalized="123456",
            estado_gft="incluido",
            estado_editorial="publicado",
            validation_errors=[],
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.cima_sync_service.CimaClient.get_by_cn",
        lambda self, cn: FakeOk(),
    )

    r = client.post(f"/cima/sync/import-batch/{batch.id}?force=true", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_cn"] == 1
    assert body["ok"] == 1


def test_cima_sync_import_batch_404(client, admin_headers):
    r = client.post(f"/cima/sync/import-batch/{uuid.uuid4()}", headers=admin_headers)
    assert r.status_code == 404
