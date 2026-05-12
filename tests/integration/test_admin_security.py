from app.core import config


def test_admin_health_returns_503_when_key_not_configured(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", None)

    response = client.get("/admin/health")

    assert response.status_code == 503
    assert response.json()["detail"] == "Admin API key is not configured"


def test_admin_health_returns_401_when_header_missing(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/admin/health")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing admin API key"


def test_admin_health_returns_403_when_header_invalid(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/admin/health", headers={"X-Admin-API-Key": "wrong"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid admin API key"


def test_admin_health_returns_ok_when_header_valid(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/admin/health", headers={"X-Admin-API-Key": "secret"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
