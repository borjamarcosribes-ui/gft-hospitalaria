import uuid
from types import SimpleNamespace

from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging
from app.services.cima_segmented_sync_service import sync_import_batch_segmented_sections


def _add_batch(db_session):
    batch = ImportBatch(filename="segmented.xlsx", status="validated")
    db_session.add(batch)
    db_session.flush()
    return batch


def _staging_row(batch_id, row_number, cn, estado_gft="incluido", estado_editorial="publicado", errors=None):
    return ImportRowStaging(
        id=uuid.uuid4(),
        batch_id=batch_id,
        row_number=row_number,
        cn_normalized=cn,
        estado_gft=estado_gft,
        estado_editorial=estado_editorial,
        validation_errors=[] if errors is None else errors,
    )


def test_cima_segmented_import_batch_syncs_only_eligible_nregistros(db_session, monkeypatch):
    batch = _add_batch(db_session)
    db_session.add_all(
        [
            _staging_row(batch.id, 1, "111111"),
            _staging_row(batch.id, 2, "111111"),
            _staging_row(batch.id, 3, "222222"),
            _staging_row(batch.id, 4, "333333"),
            _staging_row(batch.id, 5, "444444", estado_gft="excluido"),
            _staging_row(batch.id, 6, "555555", errors=["err"]),
            _staging_row(batch.id, 7, "666666", estado_gft="pendiente_revision"),
            _staging_row(batch.id, 8, "", errors=["err"]),
            _staging_row(batch.id, 9, "777777", estado_editorial=None),
        ]
    )
    db_session.add_all(
        [
            CimaMedicamentoCache(cn="111111", sync_status="ok", nregistro="70030"),
            CimaMedicamentoCache(cn="222222", sync_status="ok", nregistro="70030"),
            CimaMedicamentoCache(cn="333333", sync_status="ok", nregistro="80000"),
        ]
    )
    db_session.commit()

    calls = []

    def fake_sync(**kwargs):
        calls.append(kwargs)
        statuses = {"70030": "ok", "80000": "section_unavailable"}
        return SimpleNamespace(sync_status=statuses[kwargs["nregistro"]])

    monkeypatch.setattr("app.services.cima_segmented_sync_service.sync_cima_segmented_section", fake_sync)

    result = sync_import_batch_segmented_sections(db_session, batch.id)

    assert result["total_rows"] == 9
    assert result["eligible_cn"] == 3
    assert result["total_cn"] == 3
    assert result["eligible_nregistro"] == 2
    assert result["total_nregistro"] == 2
    assert result["ok"] == 1
    assert result["not_found"] == 0
    assert result["not_segmented"] == 0
    assert result["section_unavailable"] == 1
    assert result["error"] == 0
    assert result["skipped_excluded"] == 1
    assert result["skipped_errors"] == 2
    assert result["skipped_pending"] == 1
    assert result["skipped_missing_estado_editorial"] == 1
    assert result["skipped_missing_cima_cache"] == 0
    assert result["skipped_cima_cache_not_ok"] == 0
    assert result["skipped_missing_nregistro"] == 0
    assert result["deduplicated_rows"] == 1
    assert result["deduplicated_nregistro"] == 1
    assert [call["nregistro"] for call in calls] == ["70030", "80000"]
    assert [call["cn"] for call in calls] == ["111111", "333333"]


def test_cima_segmented_import_batch_skips_missing_cima_cache_and_bad_cache(db_session, monkeypatch):
    batch = _add_batch(db_session)
    db_session.add_all(
        [
            _staging_row(batch.id, 1, "111111"),
            _staging_row(batch.id, 2, "222222"),
            _staging_row(batch.id, 3, "333333"),
        ]
    )
    db_session.add_all(
        [
            CimaMedicamentoCache(cn="222222", sync_status="error", nregistro="70030"),
            CimaMedicamentoCache(cn="333333", sync_status="ok", nregistro=None),
        ]
    )
    db_session.commit()

    calls = []

    def fake_sync(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(sync_status="ok")

    monkeypatch.setattr("app.services.cima_segmented_sync_service.sync_cima_segmented_section", fake_sync)

    result = sync_import_batch_segmented_sections(db_session, batch.id)

    assert result["eligible_cn"] == 3
    assert result["eligible_nregistro"] == 0
    assert result["ok"] == 0
    assert result["not_found"] == 0
    assert result["not_segmented"] == 0
    assert result["section_unavailable"] == 0
    assert result["error"] == 0
    assert result["skipped_missing_cima_cache"] == 1
    assert result["skipped_cima_cache_not_ok"] == 1
    assert result["skipped_missing_nregistro"] == 1
    assert calls == []


def test_cima_segmented_import_batch_endpoint_404(client, admin_headers):
    response = client.post(f"/cima/segmented/sync/import-batch/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Import batch not found"


def test_cima_segmented_import_batch_endpoint_returns_summary(client, db_session, monkeypatch, admin_headers):
    batch = _add_batch(db_session)
    db_session.add(_staging_row(batch.id, 1, "111111"))
    db_session.add(CimaMedicamentoCache(cn="111111", sync_status="ok", nregistro="70030"))
    db_session.commit()

    monkeypatch.setattr(
        "app.services.cima_segmented_sync_service.sync_cima_segmented_section",
        lambda **kwargs: SimpleNamespace(sync_status="ok"),
    )

    response = client.post(f"/cima/segmented/sync/import-batch/{batch.id}", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == str(batch.id)
    assert body["tipo_documento"] == 1
    assert body["seccion"] == "4.1"
    assert body["total_rows"] == 1
    assert body["eligible_cn"] == 1
    assert body["eligible_nregistro"] == 1
    assert body["ok"] == 1
    assert body["error"] == 0


def test_cima_segmented_import_batch_propagates_force(client, db_session, monkeypatch, admin_headers):
    batch = _add_batch(db_session)
    db_session.add(_staging_row(batch.id, 1, "111111"))
    db_session.add(CimaMedicamentoCache(cn="111111", sync_status="ok", nregistro="70030"))
    db_session.commit()

    captured = {}

    def fake_sync(**kwargs):
        captured["force"] = kwargs["force"]
        return SimpleNamespace(sync_status="ok")

    monkeypatch.setattr("app.services.cima_segmented_sync_service.sync_cima_segmented_section", fake_sync)

    response = client.post(f"/cima/segmented/sync/import-batch/{batch.id}?force=true", headers=admin_headers)

    assert response.status_code == 200
    assert captured["force"] is True


def test_cima_segmented_import_batch_route_does_not_fall_into_nregistro_endpoint(client, db_session, monkeypatch, admin_headers):
    batch = _add_batch(db_session)
    db_session.add(_staging_row(batch.id, 1, "111111"))
    db_session.add(CimaMedicamentoCache(cn="111111", sync_status="ok", nregistro="70030"))
    db_session.commit()

    monkeypatch.setattr(
        "app.services.cima_segmented_sync_service.sync_cima_segmented_section",
        lambda **kwargs: SimpleNamespace(sync_status="not_segmented"),
    )

    response = client.post(f"/cima/segmented/sync/import-batch/{batch.id}", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == str(batch.id)
    assert body["not_segmented"] == 1
    assert "nregistro" not in body
