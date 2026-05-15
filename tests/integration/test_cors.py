import uuid

from app.core import config

CODESPACES_ORIGIN = "https://verbose-space-cod-r4vx56r7wqx72x5jv-5173.app.github.dev"
DISALLOWED_ORIGIN = "https://example.com"


def test_public_gft_preflight_allows_codespaces_origin(client):
    response = client.options(
        "/gft/medicamentos",
        headers={
            "Origin": CODESPACES_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code in {200, 204}
    assert response.headers["Access-Control-Allow-Origin"] == CODESPACES_ORIGIN


def test_admin_preflight_allows_admin_api_key_header_for_codespaces_origin(client):
    response = client.options(
        "/admin/health",
        headers={
            "Origin": CODESPACES_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Admin-API-Key",
        },
    )

    assert response.status_code in {200, 204}
    assert response.headers["Access-Control-Allow-Origin"] == CODESPACES_ORIGIN
    allowed_headers = response.headers["Access-Control-Allow-Headers"]
    assert "x-admin-api-key" in allowed_headers.lower()


def test_cors_does_not_bypass_admin_or_internal_route_security(client, monkeypatch):
    from app.api.routes import gft as gft_routes

    def stub_list_medicamentos(
        db,
        *,
        limit,
        offset,
        q=None,
        letra=None,
        principio_activo=None,
        atc=None,
    ):
        return {"total": 0, "limit": limit, "offset": offset, "items": []}

    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    monkeypatch.setattr(gft_routes, "list_medicamentos", stub_list_medicamentos)

    admin_health = client.get("/admin/health")
    imports = client.get(f"/imports/{uuid.uuid4()}")
    medicamentos = client.get("/gft/medicamentos")

    assert admin_health.status_code == 401
    assert admin_health.json()["detail"] == "Missing admin API key"
    assert imports.status_code == 401
    assert imports.json()["detail"] == "Missing admin API key"
    assert medicamentos.status_code == 200
    assert medicamentos.json() == {"total": 0, "limit": 20, "offset": 0, "items": []}


def test_disallowed_origin_does_not_receive_allow_origin_header(client):
    response = client.options(
        "/gft/medicamentos",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "Access-Control-Allow-Origin" not in response.headers
