from app.services.cima_clinical_extraction_service import extract_cima_clinical_from_html


def test_extracts_clinical_fields_from_cima_html_without_truncating_source():
    html = """
    <html><body>
      <h2>4.1 Indicaciones terapéuticas</h2>
      <p>Tratamiento de prueba indicado en adultos.</p>
      <h2>4.2 Posología y forma de administración</h2>
      <p>En insuficiencia renal ajustar según aclaramiento de creatinina.</p>
      <p>En insuficiencia hepática moderada se recomienda precaución.</p>
      <h2>4.4 Advertencias y precauciones especiales de empleo</h2>
      <p>Los pacientes en diálisis requieren vigilancia.</p>
      <h2>4.6 Fertilidad, embarazo y lactancia</h2>
      <p>Durante el embarazo debe valorarse el beneficio clínico.</p>
      <p>La lactancia debe interrumpirse si aparece riesgo para el lactante.</p>
      <h2>5.2 Propiedades farmacocinéticas</h2>
      <p>La eliminación renal puede disminuir.</p>
    </body></html>
    """

    result = extract_cima_clinical_from_html(html)

    assert result.source_status == "ok"
    assert result.indicaciones_ficha_tecnica == "Tratamiento de prueba indicado en adultos."
    assert "aclaramiento de creatinina" in result.ajuste_insuficiencia_renal
    assert "hepática moderada" in result.ajuste_insuficiencia_hepatica
    assert "embarazo" in result.precauciones_embarazo
    assert "lactancia" in result.precauciones_lactancia
    assert result.source_sections["5.2"] == "Propiedades farmacocinéticas La eliminación renal puede disminuir."
    assert "Tratamiento de prueba indicado en adultos" in result.source_text


def test_returns_no_data_and_no_informado_when_html_has_no_clinical_sections():
    result = extract_cima_clinical_from_html("<p>Texto sin apartados clínicos CIMA.</p>")

    assert result.source_status == "no_data"
    assert result.indicaciones_ficha_tecnica == "No informado"
    assert result.ajuste_insuficiencia_renal == "No informado"
    assert result.source_sections == {}
