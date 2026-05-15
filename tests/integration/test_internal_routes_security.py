import uuid

from app.core import config

ADMIN_HEADERS = {"X-Admin-API-Key": "secret"}


def test_imports_require_configured_admin_api_key(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", None)

    response = client.get(f"/imports/{uuid.uuid4()}")

    assert response.status_code == 503
    assert response.json()["detail"] == "Admin API key is not configured"


def test_imports_require_admin_header_when_key_configured(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get(f"/imports/{uuid.uuid4()}")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing admin API key"


def test_imports_reject_invalid_admin_header(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get(
        f"/imports/{uuid.uuid4()}",
        headers={"X-Admin-API-Key": "wrong"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid admin API key"


def test_imports_with_valid_admin_header_reaches_existing_logic(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get(f"/imports/{uuid.uuid4()}", headers=ADMIN_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"] == "Batch no encontrado"


def test_cima_representative_endpoint_requires_admin_header(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    missing = client.get("/cima/cache/123456")
    invalid = client.get(
        "/cima/cache/123456",
        headers={"X-Admin-API-Key": "wrong"},
    )

    assert missing.status_code == 401
    assert missing.json()["detail"] == "Missing admin API key"
    assert invalid.status_code == 403
    assert invalid.json()["detail"] == "Invalid admin API key"


def test_cima_with_valid_admin_header_reaches_existing_logic(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/cima/cache/123456", headers=ADMIN_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"] == "CIMA cache not found"


def test_bifimed_representative_endpoint_requires_admin_header(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    missing = client.get("/bifimed/cache/123456")
    invalid = client.get(
        "/bifimed/cache/123456",
        headers={"X-Admin-API-Key": "wrong"},
    )

    assert missing.status_code == 401
    assert missing.json()["detail"] == "Missing admin API key"
    assert invalid.status_code == 403
    assert invalid.json()["detail"] == "Invalid admin API key"


def test_bifimed_with_valid_admin_header_reaches_existing_logic(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/bifimed/cache/123456", headers=ADMIN_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"] == "BIFIMED cache not found"


def test_public_gft_and_health_endpoints_remain_public(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    medicamentos = client.get("/gft/medicamentos")
    html_export = client.get("/gft/export/html")
    pdf_export = client.get("/gft/export/pdf")
    health = client.get("/health")
    admin_health = client.get("/admin/health")

    assert medicamentos.status_code == 200
    assert html_export.status_code == 200
    assert pdf_export.status_code == 200
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert admin_health.status_code == 401
    assert admin_health.json()["detail"] == "Missing admin API key"
