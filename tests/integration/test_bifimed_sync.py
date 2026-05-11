from app.models.bifimed_cache import BifimedCache
from app.services.bifimed_client import BifimedFetchResult
from app.services.bifimed_sync_service import sync_bifimed_cn


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
