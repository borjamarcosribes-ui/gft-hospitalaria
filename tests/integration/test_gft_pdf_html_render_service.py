from datetime import datetime, timezone

from app.services.gft_pdf_export_service import (
    GFTPDFATCGroup,
    GFTPDFExportData,
    GFTPDFMedication,
)
from app.services.gft_pdf_html_render_service import render_gft_pdf_html


FORBIDDEN_INTERNAL_FIELDS = [
    "raw_data",
    "sync_status",
    "sync_error",
    "observaciones_internas",
    "comentario_revision",
    "revisado_por",
    "estado_gft",
    "estado_editorial",
    "metadatos de importación internos",
]


def _medication(**overrides) -> GFTPDFMedication:
    values = {
        "nombre_comercial": "Paracetamol Hospitalario",
        "principio_activo": "Paracetamol",
        "forma_farmaceutica": "Comprimido",
        "via_administracion": "Vía oral",
        "nemonico": "PARA-500",
        "cn": "123456",
        "codigo_atc": "N02BE01",
        "descripcion_atc": "Anilidas",
        "indicaciones_ficha_tecnica": "Dolor y fiebre",
        "ajuste_insuficiencia_renal": "Ajustar si procede",
        "ajuste_insuficiencia_hepatica": "Precaución en insuficiencia hepática",
        "precauciones_embarazo": "Valorar beneficio/riesgo",
        "precauciones_lactancia": "Compatible con vigilancia",
        "restricciones_hospitalarias": "Uso hospitalario",
        "observaciones_publicables": "Observación publicable de prueba",
        "situacion_financiacion_bifimed": "Financiado",
        "url_ficha_tecnica": "https://example.test/ficha/123456",
        "url_prospecto": "https://example.test/prospecto/123456",
    }
    values.update(overrides)
    return GFTPDFMedication(**values)


def _export_data(medication: GFTPDFMedication | None = None) -> GFTPDFExportData:
    child = GFTPDFATCGroup(
        codigo="N02",
        nombre="Analgésicos",
        nivel="L2",
        count=1,
        medicamentos=[medication or _medication()],
    )
    group = GFTPDFATCGroup(
        codigo="N",
        nombre="Sistema nervioso",
        nivel="L1",
        count=1,
        children=[child],
    )
    return GFTPDFExportData(
        generated_at=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
        title="Guía Farmacoterapéutica Hospitalaria",
        total_medicamentos=1,
        groups=[group],
    )


def test_render_gft_pdf_html_returns_complete_document():
    html = render_gft_pdf_html(_export_data())

    assert html.startswith("<!doctype html>")
    assert '<html lang="es">' in html
    assert '<meta charset="utf-8">' in html
    assert "<title>Guía Farmacoterapéutica Hospitalaria</title>" in html
    assert "<body>" in html
    assert "</body>" in html


def test_render_gft_pdf_html_includes_cover_index_and_medication_body():
    html = render_gft_pdf_html(_export_data())

    assert "Guía Farmacoterapéutica Hospitalaria" in html
    assert "Exportación compacta de medicamentos publicados" in html
    assert "Total de medicamentos publicados" in html
    assert "Total de medicamentos publicados:</strong> 1" in html
    assert "Fecha de generación:" in html
    assert "02/01/2026 03:04 UTC" in html


def test_render_gft_pdf_html_renders_atc_groups_and_medications():
    html = render_gft_pdf_html(_export_data())

    assert "Sistema nervioso" in html
    assert "Analgésicos" in html
    assert "N02" in html
    assert "Paracetamol Hospitalario" in html
    assert "Paracetamol" in html
    assert "Comprimido" in html
    assert "Vía oral" in html
    assert "123456" in html
    assert "N02BE01" in html
    assert "Financiado" in html
    assert "https://example.test/ficha/123456" in html
    assert "https://example.test/prospecto/123456" in html


def test_render_gft_pdf_html_preserves_no_informado_values():
    html = render_gft_pdf_html(
        _export_data(_medication(forma_farmaceutica="No informado", url_ficha_tecnica="No informado"))
    )

    assert "No informado" not in html


def test_render_gft_pdf_html_full_mode_includes_long_fields():
    html = render_gft_pdf_html(_export_data(), mode="full")
    assert "Exportación completa de medicamentos publicados" in html
    assert "Dolor y fiebre" in html
    assert "Uso hospitalario" in html


def test_render_gft_pdf_html_compact_skips_empty_parent_tables():
    html = render_gft_pdf_html(_export_data())

    assert "Sistema nervioso" in html
    assert "Analgésicos" in html
    assert html.count("<table>") == 1


def test_render_gft_pdf_html_escapes_malicious_html_content():
    html = render_gft_pdf_html(
        _export_data(
            _medication(
                nombre_comercial='<script>alert("x")</script>',
                url_prospecto='https://example.test/?q=<script>alert("x")</script>',
            )
        )
    )

    assert '<script>alert("x")</script>' not in html
    assert '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in html
    assert 'https://example.test/?q=&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in html


def test_render_gft_pdf_html_excludes_forbidden_internal_field_names():
    html = render_gft_pdf_html(_export_data())

    for field in FORBIDDEN_INTERNAL_FIELDS:
        assert field not in html


def test_render_gft_pdf_html_is_deterministic_for_same_export_data():
    export_data = _export_data()

    assert render_gft_pdf_html(export_data) == render_gft_pdf_html(export_data)
