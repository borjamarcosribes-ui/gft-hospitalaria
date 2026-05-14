import pytest

import app.api.routes.gft as gft_routes
import app.services.gft_pdf_binary_service as binary_service
from app.services.gft_pdf_binary_service import GFTPDFRenderingError, render_gft_pdf_bytes
from tests.integration.test_gft_pdf_html_export_api import FORBIDDEN_INTERNAL_FIELDS
from tests.integration.test_gft_pdf_export_service import _create_view, _insert_medicamento


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

    def fake_build(db):
        calls.append("build_gft_pdf_export_data")
        assert db is not None
        return export_data

    def fake_render(data):
        calls.append("render_gft_pdf_html")
        assert data is export_data
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
    assert '<span class="total-number">0</span>' in captured["html"]


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
