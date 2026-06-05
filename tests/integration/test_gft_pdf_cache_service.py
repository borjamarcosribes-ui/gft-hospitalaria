from dataclasses import replace
from datetime import datetime, timezone

from app.services.gft_pdf_cache_service import (
    build_gft_pdf_cache_fingerprint,
    get_cached_gft_pdf_bytes,
    get_or_render_cached_gft_pdf_bytes,
)
from tests.integration.test_gft_pdf_html_render_service import _export_data, _medication


def test_gft_pdf_cache_reuses_pdf_for_same_exportable_data(tmp_path):
    export_data = _export_data()
    calls = {"html": 0, "pdf": 0}

    def html_renderer(data, mode):
        calls["html"] += 1
        assert data is export_data
        assert mode == "narrative"
        return "<!doctype html><html><body>cache-test</body></html>"

    def pdf_renderer(html):
        calls["pdf"] += 1
        assert "cache-test" in html
        return b"%PDF-1.7\ncache-test\n"

    first = get_or_render_cached_gft_pdf_bytes(
        export_data,
        cache_dir=tmp_path,
        html_renderer=html_renderer,
        pdf_renderer=pdf_renderer,
    )
    second = get_or_render_cached_gft_pdf_bytes(
        export_data,
        cache_dir=tmp_path,
        html_renderer=html_renderer,
        pdf_renderer=pdf_renderer,
    )

    assert first == b"%PDF-1.7\ncache-test\n"
    assert second == first
    assert calls == {"html": 1, "pdf": 1}
    assert get_cached_gft_pdf_bytes(export_data, cache_dir=tmp_path) == first


def test_gft_pdf_cache_fingerprint_changes_when_exportable_data_changes():
    original = _export_data(_medication(nombre_comercial="Paracetamol Hospitalario"))
    changed = _export_data(_medication(nombre_comercial="Paracetamol Cambiado"))

    assert build_gft_pdf_cache_fingerprint(original) != build_gft_pdf_cache_fingerprint(
        changed
    )


def test_gft_pdf_cache_fingerprint_ignores_generated_at():
    original = _export_data()
    regenerated = replace(
        original,
        generated_at=datetime(2026, 6, 5, 12, 30, tzinfo=timezone.utc),
    )

    assert build_gft_pdf_cache_fingerprint(original) == build_gft_pdf_cache_fingerprint(
        regenerated
    )


def test_gft_pdf_cache_fingerprint_separates_export_modes():
    export_data = _export_data()

    assert build_gft_pdf_cache_fingerprint(
        export_data, mode="narrative"
    ) != build_gft_pdf_cache_fingerprint(export_data, mode="table")
    assert build_gft_pdf_cache_fingerprint(
        export_data, mode="compact"
    ) == build_gft_pdf_cache_fingerprint(export_data, mode="table")


def test_gft_pdf_cache_fingerprint_changes_when_atc_title_changes():
    original = _export_data()
    changed = _export_data()
    changed.groups[0].children[0].nombre = "Analgésicos modificados"

    assert build_gft_pdf_cache_fingerprint(original) != build_gft_pdf_cache_fingerprint(changed)


def test_gft_pdf_cache_fingerprint_changes_when_atc_catalog_source_changes(monkeypatch):
    export_data = _export_data()
    original = build_gft_pdf_cache_fingerprint(export_data)

    monkeypatch.setattr(
        "app.services.gft_pdf_cache_service.atc_catalog_fingerprint",
        lambda: "catalogo-atc-modificado",
    )

    assert build_gft_pdf_cache_fingerprint(export_data) != original
