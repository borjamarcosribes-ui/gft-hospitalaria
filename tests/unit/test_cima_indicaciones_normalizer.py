from app.services.cima_indicaciones_normalizer import normalize_cima_indicaciones


def test_normalize_with_colon_headers():
    text = "Artritis reumatoide: Tratamiento en adultos.\nEnfermedad de Crohn: Indicado en pacientes con respuesta insuficiente."
    out = normalize_cima_indicaciones(text)
    assert len(out) == 2
    assert out[0]["titulo"] == "Artritis reumatoide"
    assert out[0]["confidence"] == "alta"


def test_normalize_with_bullets():
    text = "- Artritis psoriásica en adultos\n- Espondiloartritis axial activa"
    out = normalize_cima_indicaciones(text)
    assert len(out) == 2
    assert all(item["confidence"] == "media" for item in out)


def test_normalize_lines_split():
    text = "Adultos con insuficiencia cardiaca sintomática.\nPoblación pediátrica con diagnóstico confirmado."
    out = normalize_cima_indicaciones(text)
    assert len(out) == 2


def test_normalize_unstructured_fallback():
    text = "Indicado para el tratamiento de pacientes según ficha técnica vigente"
    out = normalize_cima_indicaciones(text)
    assert len(out) == 1
    assert out[0]["titulo"] == "Indicaciones terapéuticas"
    assert out[0]["confidence"] == "baja"


def test_normalize_adultos_pediatrica():
    text = "Adultos: Tratamiento de mantenimiento.\nPoblación pediátrica: Uso restringido a especialistas."
    out = normalize_cima_indicaciones(text)
    assert [item["titulo"] for item in out] == ["Adultos", "Población pediátrica"]


def test_normalize_biologic_multi_pathologies():
    text = "1) Artritis reumatoide activa en adultos.\n2) Colitis ulcerosa activa de moderada a grave.\n3) Enfermedad de Crohn activa de moderada a grave."
    out = normalize_cima_indicaciones(text)
    assert len(out) == 3
    assert out[1]["texto"].startswith("Colitis ulcerosa")
