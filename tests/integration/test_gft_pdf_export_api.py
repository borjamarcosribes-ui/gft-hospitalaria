import pytest

import app.api.routes.gft as gft_routes
import app.services.gft_pdf_binary_service as binary_service
from app.services.gft_pdf_binary_service import GFTPDFRenderingError, render_gft_pdf_bytes
from tests.integration.test_gft_pdf_html_export_api import FORBIDDEN_INTERNAL_FIELDS
from tests.integration.test_gft_pdf_export_service import _create_view, _insert_medicamento


@pytest.fixture(autouse=True)
def _isolated_pdf_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GFT_PDF_CACHE_DIR", str(tmp_path / "pdf-cache"))


def test_gft_export_pdf_endpoint_returns_attachment_pdf(client, db_session, monkeypatch):
    _insert_medicamento(db_session, "800001", nombre="Medicamento PDF")
    _create_view(db_session)
    monkeypatch.setattr(gft_routes, "render_gft_pdf_bytes", lambda html: b"%PDF-1.7\nendpoint-test\n")

    response = client.get("/gft/export/pdf")

    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]
    content_disposition = response.headers["content-disposition"]
    assert "attachment" in content_disposition
    assert "gft-hospitalaria.pdf" in content_disposition
    assert response.content.startswith(b"%PDF")


def test_gft_export_pdf_endpoint_uses_existing_export_html_pdf_chain(client, monkeypatch):
    calls = []
    export_data = object()
    html = "<!doctype html><html><body>same-chain</body></html>"

    def fake_build(db, mode="narrative"):
        calls.append("build_gft_pdf_export_data")
        assert db is not None
        assert mode == "narrative"
        return export_data

    def fake_render(data, mode="narrative"):
        calls.append("render_gft_pdf_html")
        assert data is export_data
        assert mode == "narrative"
        return html

    def fake_pdf_bytes(received_html):
        calls.append("render_gft_pdf_bytes")
        assert received_html == html
        return b"%PDF-1.7\nchain-test\n"

    monkeypatch.setattr(gft_routes, "build_gft_pdf_export_data", fake_build)
    monkeypatch.setattr(gft_routes, "render_gft_pdf_html", fake_render)
    monkeypatch.setattr(gft_routes, "render_gft_pdf_bytes", fake_pdf_bytes)

    response = client.get("/gft/export/pdf")

    assert response.status_code == 200
    assert calls == ["build_gft_pdf_export_data", "render_gft_pdf_html", "render_gft_pdf_bytes"]
    assert response.content.startswith(b"%PDF")


def test_gft_export_pdf_endpoint_returns_503_when_pdf_renderer_is_unavailable(
    client, db_session, monkeypatch
):
    _insert_medicamento(db_session, "820001", nombre="Medicamento con PDF no disponible")
    _create_view(db_session)

    def fake_pdf_bytes(html):
        raise GFTPDFRenderingError("native renderer traceback detail must stay internal")

    monkeypatch.setattr(gft_routes, "render_gft_pdf_bytes", fake_pdf_bytes)

    response = client.get("/gft/export/pdf")

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "PDF rendering is unavailable. Use /gft/export/html or install "
            "PDF rendering dependencies."
        )
    }
    assert "traceback" not in response.text.lower()
    assert "native renderer" not in response.text


def test_gft_export_html_remains_available_when_pdf_renderer_is_unavailable(
    client, db_session, monkeypatch
):
    _insert_medicamento(db_session, "820002", nombre="Medicamento HTML alternativo")
    _create_view(db_session)

    def fake_pdf_bytes(html):
        raise GFTPDFRenderingError("PDF unavailable")

    monkeypatch.setattr(gft_routes, "render_gft_pdf_bytes", fake_pdf_bytes)

    response = client.get("/gft/export/html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Medicamento HTML alternativo" in response.text


def test_gft_export_pdf_endpoint_returns_valid_empty_pdf(client, db_session, monkeypatch):
    _create_view(db_session)
    captured = {}

    def fake_pdf_bytes(html):
        captured["html"] = html
        return b"%PDF-1.7\nempty-test\n"

    monkeypatch.setattr(gft_routes, "render_gft_pdf_bytes", fake_pdf_bytes)

    response = client.get("/gft/export/pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert "No hay medicamentos publicados." in captured["html"]
    assert "Total de medicamentos publicados:</strong> 0" in captured["html"]


def test_gft_export_pdf_endpoint_reuses_cached_pdf_for_same_data(
    client, db_session, monkeypatch
):
    _insert_medicamento(db_session, "840001", nombre="Medicamento cacheado")
    _create_view(db_session)
    calls = {"pdf": 0}

    def fake_pdf_bytes(html):
        calls["pdf"] += 1
        assert "Medicamento cacheado" in html
        return b"%PDF-1.7\ncached-endpoint\n"

    monkeypatch.setattr(gft_routes, "render_gft_pdf_bytes", fake_pdf_bytes)

    first = client.get("/gft/export/pdf")
    second = client.get("/gft/export/pdf")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.content == second.content
    assert calls["pdf"] == 1


def test_gft_export_pdf_rejects_invalid_mode(client):
    response = client.get("/gft/export/pdf?mode=invalid")
    assert response.status_code == 400


def test_gft_export_html_accepts_full_mode(client, db_session):
    _insert_medicamento(db_session, "830001", nombre="Medicamento FULL")
    _create_view(db_session)
    response = client.get("/gft/export/html?mode=full")
    assert response.status_code == 200
    assert "Exportación completa de medicamentos publicados" in response.text


def test_gft_export_html_accepts_table_mode(client, db_session):
    _insert_medicamento(db_session, "830002", nombre="Medicamento TABLE")
    _create_view(db_session)
    response = client.get("/gft/export/html?mode=table")
    assert response.status_code == 200
    assert "Exportación técnica tabular de medicamentos publicados" in response.text


def test_gft_export_pdf_html_passed_to_engine_does_not_expose_internal_fields(client, db_session, monkeypatch):
    _insert_medicamento(db_session, "810001", nombre="Medicamento público")
    _create_view(db_session)
    captured = {}

    def fake_pdf_bytes(html):
        captured["html"] = html
        return b"%PDF-1.7\nno-internals-test\n"

    monkeypatch.setattr(gft_routes, "render_gft_pdf_bytes", fake_pdf_bytes)

    response = client.get("/gft/export/pdf")

    assert response.status_code == 200
    for field in FORBIDDEN_INTERNAL_FIELDS:
        assert field not in captured["html"]


def test_render_gft_pdf_bytes_returns_pdf_when_weasyprint_is_available():
    pytest.importorskip("weasyprint", reason="WeasyPrint is not installed in this environment")

    pdf = render_gft_pdf_bytes("<!doctype html><html><body><h1>GFT test</h1></body></html>")

    assert pdf.startswith(b"%PDF")


def test_render_gft_pdf_bytes_raises_clear_error_when_weasyprint_is_missing(monkeypatch):
    monkeypatch.setattr(binary_service, "find_spec", lambda name: None if name == "weasyprint" else None)

    with pytest.raises(GFTPDFRenderingError, match="WeasyPrint is required"):
        render_gft_pdf_bytes("<!doctype html><html><body>missing dependency</body></html>")


def test_render_gft_pdf_bytes_raises_clear_error_when_weasyprint_import_fails(monkeypatch):
    def fake_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise OSError("missing native library")
        return original_import(name, *args, **kwargs)

    original_import = __import__
    monkeypatch.setattr(
        binary_service,
        "find_spec",
        lambda name: object() if name == "weasyprint" else None,
    )
    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(GFTPDFRenderingError, match="could not be loaded"):
        render_gft_pdf_bytes("<!doctype html><html><body>import failure</body></html>")


def test_gft_atc_catalog_endpoint_returns_backend_catalog(client):
    response = client.get("/gft/atc/catalog")

    assert response.status_code == 200
    items = {item["code"]: item for item in response.json()["items"]}
    assert items["A"]["title"] == "Tracto alimentario y metabolismo"
    assert items["A02"]["title"] == "Agentes para el tratamiento de alteraciones causadas por ácidos"
