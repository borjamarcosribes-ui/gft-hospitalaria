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
    assert "Guía narrativa de medicamentos publicados ordenada por ATC" in html
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
    assert "123456" in html
    assert "N02BE01" in html
    assert "Dolor y fiebre" in html
    assert "Ajustar si procede" in html
    assert "Precaución en insuficiencia hepática" in html
    assert "Paracetamol Hospitalario — CN 123456" in html
    assert "Restricciones hospitalarias:" in html


def test_render_gft_pdf_html_renders_required_fields_even_when_no_informado():
    html = render_gft_pdf_html(
        _export_data(
            _medication(
                principio_activo="No informado",
                forma_farmaceutica="No informado",
                via_administracion="",
                nemonico=None,
                codigo_atc="No informado",
                situacion_financiacion_bifimed="No informado",
                url_ficha_tecnica="No informado",
            )
        )
    )

    assert "Principio activo:" in html
    assert "Forma farmacéutica:" in html
    assert "Vía:" in html
    assert "Nemónico:" in html
    assert "ATC:" in html
    assert "Financiación BIFIMED:" in html
    assert html.count("No informado") >= 6


def test_render_gft_pdf_html_required_fields_keep_expected_order():
    html = render_gft_pdf_html(_export_data())

    title_idx = html.index("Paracetamol Hospitalario — CN 123456")
    principio_idx = html.index("Principio activo:")
    forma_idx = html.index("Forma farmacéutica:")
    via_idx = html.index("Vía:")
    nemonico_idx = html.index("Nemónico:")
    atc_idx = html.index("ATC:")
    financiacion_idx = html.index("Financiación BIFIMED:")
    cima_idx = html.index("Indicaciones ficha técnica/CIMA:")

    assert title_idx < principio_idx < forma_idx < via_idx < nemonico_idx < atc_idx < financiacion_idx < cima_idx


def test_render_gft_pdf_html_full_mode_includes_long_fields():
    html = render_gft_pdf_html(_export_data(), mode="full")
    assert "Exportación completa de medicamentos publicados" in html
    assert "Dolor y fiebre" in html
    assert "Uso hospitalario" in html


def test_render_gft_pdf_html_table_mode_skips_empty_parent_tables():
    html = render_gft_pdf_html(_export_data(), mode="table")

    assert "Sistema nervioso" in html
    assert "Analgésicos" in html
    assert html.count("<table>") == 1
    assert "Guía narrativa de medicamentos publicados ordenada por ATC" not in html
    assert "Comprimido" in html


def test_render_gft_pdf_html_narrative_has_no_table():
    html = render_gft_pdf_html(_export_data())
    assert "<table>" not in html


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
    assert 'https://example.test/?q=&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' not in html


def test_render_gft_pdf_html_excludes_forbidden_internal_field_names():
    html = render_gft_pdf_html(_export_data())

    for field in FORBIDDEN_INTERNAL_FIELDS:
        assert field not in html


def test_render_gft_pdf_html_is_deterministic_for_same_export_data():
    export_data = _export_data()

    assert render_gft_pdf_html(export_data) == render_gft_pdf_html(export_data)


def test_render_gft_pdf_html_narrative_uses_auto_summary_values_as_fallback():
    html = render_gft_pdf_html(
        _export_data(
            _medication(
                resumen_clinico_auto={"ajuste_renal": "Ajuste renal automático"},
                ajuste_insuficiencia_renal="No informado",
            )
        )
    )
    assert "Ajuste renal automático" in html


def test_render_gft_pdf_html_narrative_prioritizes_full_cima_text_over_summary():
    long_cima = "Indicación completa de ficha técnica. " + ("Detalle clínico extenso. " * 30) + "FRASE-FINAL-CIMA"

    html = render_gft_pdf_html(
        _export_data(
            _medication(
                resumen_clinico_auto={"indicaciones": "Resumen corto"},
                indicaciones_ficha_tecnica=long_cima,
            )
        )
    )

    assert "FRASE-FINAL-CIMA" in html
    assert long_cima in html
    assert "Resumen corto" not in html


def test_render_gft_pdf_html_narrative_prioritizes_full_source_clinical_fields_over_summary():
    html = render_gft_pdf_html(
        _export_data(
            _medication(
                resumen_clinico_auto={
                    "ajuste_renal": "Resumen renal",
                    "ajuste_hepatico": "Resumen hepático",
                    "embarazo": "Resumen embarazo",
                    "lactancia": "Resumen lactancia",
                },
                ajuste_insuficiencia_renal="Texto renal fuente completo",
                ajuste_insuficiencia_hepatica="Texto hepático fuente completo",
                precauciones_embarazo="Texto embarazo fuente completo",
                precauciones_lactancia="Texto lactancia fuente completo",
            )
        )
    )

    assert "Texto renal fuente completo" in html
    assert "Texto hepático fuente completo" in html
    assert "Texto embarazo fuente completo" in html
    assert "Texto lactancia fuente completo" in html
    assert "Resumen renal" not in html
    assert "Resumen hepático" not in html
    assert "Resumen embarazo" not in html
    assert "Resumen lactancia" not in html


def test_render_gft_pdf_html_narrative_hides_document_urls():
    html = render_gft_pdf_html(_export_data())
    assert "https://example.test/ficha/123456" not in html
    assert "https://example.test/prospecto/123456" not in html


def test_render_gft_pdf_html_renders_bifimed_indicaciones_block():
    html = render_gft_pdf_html(
        _export_data(
            _medication(
                indicaciones_bifimed=[
                    {
                        "indicacion": "Tratamiento de mantenimiento en pacientes adultos.",
                        "situacion_financiacion": "Financiado",
                        "resolucion": "Uso autorizado en hospital.",
                    }
                ]
            )
        )
    )
    assert "Indicaciones BIFIMED:" in html
    assert "Tratamiento de mantenimiento en pacientes adultos." in html
    assert "Financiación: Financiada" in html
    assert "Situación: Uso autorizado en hospital." in html


def test_render_gft_pdf_html_narrative_keeps_long_clinical_fields_complete_without_ellipsis():
    long_cima = "Indicación CIMA inicial. " + ("Texto clínico completo sin recorte. " * 40) + "FINAL-CIMA"
    long_renal = "Ajuste renal detallado. " + ("Control periódico de función renal. " * 25) + "FINAL-RENAL"
    long_hepatica = "Ajuste hepático detallado. " + ("Vigilar transaminasas y respuesta clínica. " * 25) + "FINAL-HEPATICA"
    long_embarazo = "Embarazo: " + ("evaluar beneficio/riesgo individual. " * 25) + "FINAL-EMBARAZO"
    long_lactancia = "Lactancia: " + ("monitorizar tolerancia del lactante. " * 25) + "FINAL-LACTANCIA"
    long_restricciones = "Restricciones: " + ("uso protocolizado por comisión. " * 25) + "FINAL-RESTRICCIONES"

    html = render_gft_pdf_html(
        _export_data(
            _medication(
                indicaciones_ficha_tecnica=long_cima,
                ajuste_insuficiencia_renal=long_renal,
                ajuste_insuficiencia_hepatica=long_hepatica,
                precauciones_embarazo=long_embarazo,
                precauciones_lactancia=long_lactancia,
                restricciones_hospitalarias=long_restricciones,
            )
        )
    )

    assert long_cima in html
    assert long_renal in html
    assert long_hepatica in html
    assert long_embarazo in html
    assert long_lactancia in html
    assert long_restricciones in html
    assert "…" not in html


def test_render_gft_pdf_html_narrative_uses_prominent_medication_title_structure():
    html = render_gft_pdf_html(_export_data())

    assert '<div class="med-title">Paracetamol Hospitalario — CN 123456</div>' in html
    assert ".med-title { font-weight: 700; font-size: 12px;" in html


def test_render_gft_pdf_html_narrative_avoids_closed_card_borders_and_css_clamps():
    html = render_gft_pdf_html(_export_data())

    assert ".med-card { border-left: 3px solid #d8e7f2;" in html
    assert ".med-card { border: 1px solid" not in html
    assert "max-height" not in html
    assert "overflow: hidden" not in html
    assert "line-clamp" not in html


def test_render_gft_pdf_html_renders_complete_bifimed_indicaciones_without_truncation():
    long_indicacion = "Tratamiento de mantenimiento. " + ("Indicación autorizada con detalle clínico. " * 35) + "FINAL-BIFIMED"
    html = render_gft_pdf_html(
        _export_data(
            _medication(
                indicaciones_bifimed=[
                    {
                        "indicacion": long_indicacion,
                        "situacion_financiacion": "Financiado",
                        "resolucion": "Resolución completa disponible.",
                    }
                ]
            )
        )
    )

    assert long_indicacion in html
    assert "FINAL-BIFIMED" in html
    assert "…" not in html


def test_render_gft_pdf_html_renders_bifimed_indicacion_autorizada_key():
    html = render_gft_pdf_html(
        _export_data(
            _medication(
                indicaciones_bifimed=[
                    {
                        "indicacion_autorizada": "Tratamiento autorizado completo de prueba",
                        "situacion_financiacion": "Financiada",
                    }
                ]
            )
        )
    )

    assert "Tratamiento autorizado completo de prueba" in html
    assert "Financiación: Financiada" in html


def test_render_gft_pdf_html_renders_bifimed_string_indication():
    html = render_gft_pdf_html(
        _export_data(_medication(indicaciones_bifimed=["Indicación BIFIMED como texto libre"]))
    )

    assert "Indicación BIFIMED como texto libre" in html
    assert "Financiación: No informado" in html


def test_render_gft_pdf_html_renders_bifimed_nested_indications_list():
    html = render_gft_pdf_html(
        _export_data(
            _medication(
                indicaciones_bifimed={
                    "indicaciones_autorizadas": [
                        {
                            "texto": "Indicación BIFIMED anidada completa",
                            "financiada": True,
                            "estado": "Aprobada",
                        }
                    ]
                }
            )
        )
    )

    assert "Indicación BIFIMED anidada completa" in html
    assert "Financiación: Financiada" in html
    assert "Situación: Aprobada" in html
