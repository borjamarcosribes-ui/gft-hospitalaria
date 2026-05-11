from types import SimpleNamespace
from uuid import uuid4

from app.models.bifimed_cache import BifimedCache
from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging
from app.services.bifimed_client import BifimedFetchResult
from app.services.bifimed_sync_service import sync_bifimed_cn, sync_import_batch


def _bifimed_data(
    cn="661406",
    situacion="Si",
    estado="ALTA",
    aportacion="NORMAL",
    subgrupo="M01AE01 - Ibuprofeno",
):
    return {
        "situacion_financiacion": situacion,
        "condiciones_financiacion_restringidas": "Visado",
        "condiciones_especiales_financiacion": "Especial",
        "estado_nomenclator": estado,
        "aportacion_usuario": aportacion,
        "subgrupo_atc": subgrupo,
        "detalle_financiacion_json": {"Código nacional": cn},
    }


def test_sync_bifimed_cn_ok(db_session, monkeypatch):
    def fake_get_by_cn(self, cn):
        return BifimedFetchResult(
            status="ok",
            data=_bifimed_data(cn=cn),
            raw_payload={"html": "<html>ok</html>"},
        )

    monkeypatch.setattr(
        "app.services.bifimed_sync_service.BifimedClient.get_by_cn", fake_get_by_cn
    )

    row = sync_bifimed_cn(db_session, "661406")

    assert row.cn == "661406"
    assert row.situacion_financiacion == "Si"
    assert row.estado_nomenclator == "ALTA"
    assert row.aportacion_usuario == "NORMAL"
    assert row.subgrupo_atc == "M01AE01 - Ibuprofeno"
    assert row.detalle_financiacion_json["Código nacional"] == "661406"
    assert row.raw_data == {"html": "<html>ok</html>"}
    assert row.sync_status == "ok"
    assert row.sync_error is None
    assert row.last_synced_at is not None


def test_sync_bifimed_cn_not_found(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.bifimed_sync_service.BifimedClient.get_by_cn",
        lambda self, cn: BifimedFetchResult(status="not_found"),
    )

    row = sync_bifimed_cn(db_session, "661406")

    assert row.sync_status == "not_found"
    assert row.sync_error is None


def test_sync_bifimed_cn_error(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.bifimed_sync_service.BifimedClient.get_by_cn",
        lambda self, cn: BifimedFetchResult(status="error", error="timeout"),
    )

    row = sync_bifimed_cn(db_session, "661406")

    assert row.sync_status == "error"
    assert row.sync_error == "timeout"


def test_sync_bifimed_cn_uses_cache_when_not_forced(db_session, monkeypatch):
    calls = {"count": 0}

    def fake_get_by_cn(self, cn):
        calls["count"] += 1
        return BifimedFetchResult(
            status="ok",
            data=_bifimed_data(cn=cn),
            raw_payload={"html": "A"},
        )

    monkeypatch.setattr(
        "app.services.bifimed_sync_service.BifimedClient.get_by_cn", fake_get_by_cn
    )

    first = sync_bifimed_cn(db_session, "661406")
    second = sync_bifimed_cn(db_session, "661406", force=False)

    assert first.cn == second.cn == "661406"
    assert calls["count"] == 1


def test_sync_bifimed_cn_force_refreshes_existing_row(db_session, monkeypatch):
    results = [
        BifimedFetchResult(
            status="ok",
            data=_bifimed_data(situacion="Si"),
            raw_payload={"html": "A"},
        ),
        BifimedFetchResult(
            status="ok",
            data=_bifimed_data(situacion="No incluido"),
            raw_payload={"html": "B"},
        ),
    ]

    def fake_get_by_cn(self, cn):
        return results.pop(0)

    monkeypatch.setattr(
        "app.services.bifimed_sync_service.BifimedClient.get_by_cn", fake_get_by_cn
    )

    sync_bifimed_cn(db_session, "661406")
    row = sync_bifimed_cn(db_session, "661406", force=True)

    assert row.situacion_financiacion == "No incluido"
    assert row.raw_data == {"html": "B"}


def test_bifimed_sync_endpoint(client, monkeypatch):
    def fake_get_by_cn(self, cn):
        return BifimedFetchResult(
            status="ok",
            data=_bifimed_data(cn=cn),
            raw_payload={"html": "<html>ok</html>"},
        )

    monkeypatch.setattr(
        "app.services.bifimed_sync_service.BifimedClient.get_by_cn", fake_get_by_cn
    )

    response = client.post("/bifimed/sync/661406")

    assert response.status_code == 200
    assert response.json() == {
        "cn": "661406",
        "sync_status": "ok",
        "situacion_financiacion": "Si",
        "estado_nomenclator": "ALTA",
    }


def test_bifimed_sync_endpoint_invalid_cn(client):
    response = client.post("/bifimed/sync/abc")

    assert response.status_code == 400
    assert response.json()["detail"] == "CN inválido"


def test_bifimed_cache_endpoint(client, db_session):
    db_session.add(
        BifimedCache(
            cn="661406",
            situacion_financiacion="Si",
            estado_nomenclator="ALTA",
            sync_status="ok",
        )
    )
    db_session.commit()

    response = client.get("/bifimed/cache/661406")

    assert response.status_code == 200
    body = response.json()
    assert body["cn"] == "661406"
    assert body["situacion_financiacion"] == "Si"
    assert body["estado_nomenclator"] == "ALTA"
    assert body["sync_status"] == "ok"


def test_bifimed_cache_endpoint_404(client):
    response = client.get("/bifimed/cache/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "BIFIMED cache not found"


def test_bifimed_cache_endpoint_invalid_cn(client):
    response = client.get("/bifimed/cache/abc")

    assert response.status_code == 400
    assert response.json()["detail"] == "CN inválido"


def _create_import_batch(db_session):
    batch = ImportBatch(filename="bifimed.xlsx", sha256="test-sha")
    db_session.add(batch)
    db_session.commit()
    db_session.refresh(batch)
    return batch


def _add_staging_row(
    db_session,
    batch,
    row_number,
    cn_normalized,
    estado_gft="incluido",
    estado_editorial="publicado",
    validation_errors=None,
):
    row = ImportRowStaging(
        batch_id=batch.id,
        row_number=row_number,
        cn_raw=cn_normalized,
        cn_normalized=cn_normalized,
        estado_gft=estado_gft,
        estado_editorial=estado_editorial,
        validation_errors=validation_errors or [],
        validation_warnings=[],
        raw_payload={},
    )
    db_session.add(row)
    return row


def test_sync_bifimed_import_batch_syncs_only_eligible_included_rows(
    db_session, monkeypatch
):
    batch = _create_import_batch(db_session)
    _add_staging_row(db_session, batch, 1, "111111")
    _add_staging_row(db_session, batch, 2, "111111")
    _add_staging_row(db_session, batch, 3, "222222")
    _add_staging_row(db_session, batch, 4, "333333")
    _add_staging_row(db_session, batch, 5, "444444", estado_gft="excluido")
    _add_staging_row(db_session, batch, 6, "555555", validation_errors=["bad"])
    _add_staging_row(db_session, batch, 7, "666666", estado_gft="pendiente_revision")
    _add_staging_row(db_session, batch, 8, "", validation_errors=["bad"])
    _add_staging_row(db_session, batch, 9, "777777", estado_editorial=None)
    db_session.commit()

    statuses = {"111111": "ok", "222222": "not_found", "333333": "error"}
    calls = []

    def fake_sync_bifimed_cn(db, cn, force=False):
        calls.append((cn, force))
        return SimpleNamespace(sync_status=statuses[cn])

    monkeypatch.setattr(
        "app.services.bifimed_sync_service.sync_bifimed_cn", fake_sync_bifimed_cn
    )

    summary = sync_import_batch(db_session, batch.id)

    assert calls == [("111111", False), ("222222", False), ("333333", False)]
    assert summary["batch_id"] == str(batch.id)
    assert summary["eligible_cn"] == 3
    assert summary["total_cn"] == 3
    assert summary["total_rows"] == 9
    assert summary["ok"] == 1
    assert summary["not_found"] == 1
    assert summary["error"] == 1
    assert summary["skipped_excluded"] == 1
    assert summary["skipped_errors"] == 2
    assert summary["skipped_pending"] == 1
    assert summary["skipped_missing_estado_editorial"] == 1
    assert summary["skipped_missing_cn"] == 0
    assert summary["deduplicated_rows"] == 1


def test_sync_bifimed_import_batch_does_not_call_when_no_eligible_cn(
    db_session, monkeypatch
):
    batch = _create_import_batch(db_session)
    _add_staging_row(db_session, batch, 1, "111111", estado_gft="excluido")
    _add_staging_row(db_session, batch, 2, "222222", estado_gft="pendiente_revision")
    _add_staging_row(db_session, batch, 3, "333333", validation_errors=["bad"])
    db_session.commit()

    calls = []

    def fake_sync_bifimed_cn(db, cn, force=False):
        calls.append((cn, force))
        return SimpleNamespace(sync_status="ok")

    monkeypatch.setattr(
        "app.services.bifimed_sync_service.sync_bifimed_cn", fake_sync_bifimed_cn
    )

    summary = sync_import_batch(db_session, batch.id)

    assert summary["eligible_cn"] == 0
    assert summary["total_cn"] == 0
    assert summary["ok"] == 0
    assert summary["not_found"] == 0
    assert summary["error"] == 0
    assert calls == []


def test_bifimed_import_batch_endpoint_404(client):
    response = client.post(f"/bifimed/sync/import-batch/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Import batch not found"


def test_bifimed_import_batch_endpoint_returns_summary(client, db_session, monkeypatch):
    batch = _create_import_batch(db_session)
    expected = {
        "batch_id": str(batch.id),
        "eligible_cn": 1,
        "total_cn": 1,
        "total_rows": 1,
        "ok": 1,
        "not_found": 0,
        "error": 0,
        "skipped_errors": 0,
        "skipped_missing_cn": 0,
        "skipped_pending": 0,
        "skipped_excluded": 0,
        "skipped_missing_estado_editorial": 0,
        "deduplicated_rows": 0,
    }

    def fake_sync_import_batch(db, batch_id, force=False):
        assert batch_id == batch.id
        assert force is False
        return expected

    monkeypatch.setattr(
        "app.api.routes.bifimed.sync_import_batch", fake_sync_import_batch
    )

    response = client.post(f"/bifimed/sync/import-batch/{batch.id}")

    assert response.status_code == 200
    assert response.json() == expected


def test_sync_bifimed_import_batch_propagates_force(db_session, monkeypatch):
    batch = _create_import_batch(db_session)
    _add_staging_row(db_session, batch, 1, "111111")
    db_session.commit()
    calls = []

    def fake_sync_bifimed_cn(db, cn, force=False):
        calls.append((cn, force))
        return SimpleNamespace(sync_status="ok")

    monkeypatch.setattr(
        "app.services.bifimed_sync_service.sync_bifimed_cn", fake_sync_bifimed_cn
    )

    summary = sync_import_batch(db_session, batch.id, force=True)

    assert calls == [("111111", True)]
    assert summary["ok"] == 1
