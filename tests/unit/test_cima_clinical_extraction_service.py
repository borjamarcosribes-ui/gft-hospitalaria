from app.services.cima_clinical_extraction_service import NO_INFORMADO, extract_clinical_fields_from_html


HTML_ALL_FIELDS = """
<html><head><style>.x{}</style><script>ignore()</script></head><body>
<h2>4.1 Indicaciones terapéuticas</h2>
<p>ABILIFY MAINTENA está indicado para el tratamiento de mantenimiento de la esquizofrenia en pacientes adultos estabilizados.</p>
<h2>4.2 Posología y forma de administración</h2>
<p>No es necesario ajustar la dosis en pacientes con insuficiencia renal.</p>
<p>Insuficiencia hepática: no es necesario ajustar la dosis en pacientes con insuficiencia hepática leve o moderada.</p>
<h2>4.4 Advertencias y precauciones especiales de empleo</h2>
<p>Se recomienda vigilar la función renal en pacientes con nefropatía previa.</p>
<h2>4.6 Fertilidad, embarazo y lactancia</h2>
<p>Embarazo</p>
<p>No debe utilizarse durante el embarazo salvo que el beneficio esperado justifique el riesgo potencial para el feto.</p>
<p>Lactancia</p>
<p>Se desconoce si se excreta en leche materna; debe decidirse si interrumpir la lactancia.</p>
<h2>4.7 Efectos sobre la capacidad para conducir</h2>
<p>Fin.</p>
<h2>5.2 Propiedades farmacocinéticas</h2>
<p>El aclaramiento de creatinina no modificó de forma relevante la exposición.</p>
</body></html>
"""


def test_extracts_all_clinical_fields_from_cima_html_sections():
    result = extract_clinical_fields_from_html(HTML_ALL_FIELDS, source_url="https://example.test/ft.html")

    assert result.status == "ok"
    assert result.indicaciones_ficha_tecnica.startswith("ABILIFY MAINTENA está indicado")
    assert "insuficiencia renal" in result.ajuste_insuficiencia_renal
    assert "función renal" in result.ajuste_insuficiencia_renal
    assert "insuficiencia hepática" in result.ajuste_insuficiencia_hepatica
    assert result.precauciones_embarazo == "No debe utilizarse durante el embarazo salvo que el beneficio esperado justifique el riesgo potencial para el feto."
    assert "leche materna" in result.precauciones_lactancia
    assert set(result.extracted_sections) >= {"4.1", "4.2", "4.4", "4.6"}


def test_extracts_41_and_46_keyword_paragraphs_without_subheadings():
    html = """
    <h3>4.1. INDICACIONES TERAPÉUTICAS</h3>
    <p>Indicado para el tratamiento de la enfermedad de prueba.</p>
    <h3>4.2 Posología</h3><p>Sin menciones relevantes.</p>
    <h3>4.6 Fertilidad, embarazo y lactancia</h3>
    <p>Las mujeres embarazadas no deben recibir el medicamento salvo necesidad clínica.</p>
    <p>Se desconoce si el principio activo pasa a leche materna durante la lactancia.</p>
    <h3>4.7 Conducción</h3><p>No aplica.</p>
    """

    result = extract_clinical_fields_from_html(html)

    assert result.status == "partial"
    assert result.indicaciones_ficha_tecnica == "Indicado para el tratamiento de la enfermedad de prueba."
    assert "embarazadas" in result.precauciones_embarazo
    assert "leche materna" in result.precauciones_lactancia
    assert result.ajuste_insuficiencia_renal == NO_INFORMADO


def test_no_clinical_sections_returns_no_data_without_inventing():
    result = extract_clinical_fields_from_html("<html><body><h1>1. Datos generales</h1><p>Texto administrativo.</p></body></html>")

    assert result.status == "no_data"
    assert result.indicaciones_ficha_tecnica == NO_INFORMADO
    assert result.precauciones_lactancia == NO_INFORMADO
    assert result.useful_fields == {}


def test_multiple_renal_and_hepatic_paragraphs_are_preserved_without_truncation():
    long_renal = "En insuficiencia renal " + "se conserva este texto fuente literal. " * 80
    long_hepatic = "En insuficiencia hepática " + "se conserva este texto fuente literal. " * 80
    html = f"""
    <h2>4.2\tPosología y forma de administración</h2>
    <p>{long_renal}</p>
    <p>{long_hepatic}</p>
    <h2>4.4 Advertencias y precauciones especiales de empleo</h2>
    <p>Los pacientes en hemodiálisis requieren vigilancia estrecha.</p>
    <p>Se han observado elevaciones de transaminasas en pacientes vulnerables.</p>
    <h2>4.6 Fertilidad, embarazo y lactancia</h2><p>No contiene palabras clave.</p>
    """

    result = extract_clinical_fields_from_html(html)

    assert long_renal in result.ajuste_insuficiencia_renal
    assert "Los pacientes en hemodiálisis requieren vigilancia estrecha." in result.ajuste_insuficiencia_renal
    assert long_hepatic in result.ajuste_insuficiencia_hepatica
    assert "transaminasas" in result.ajuste_insuficiencia_hepatica
    assert "…" not in result.ajuste_insuficiencia_renal
    assert "…" not in result.ajuste_insuficiencia_hepatica


def test_abilify_like_fixture_is_generic_section_extraction_not_cn_specific():
    result = extract_clinical_fields_from_html(HTML_ALL_FIELDS)

    assert result.indicaciones_ficha_tecnica == (
        "ABILIFY MAINTENA está indicado para el tratamiento de mantenimiento de la esquizofrenia "
        "en pacientes adultos estabilizados."
    )
