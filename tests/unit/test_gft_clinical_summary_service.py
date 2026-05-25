from app.services.gft_clinical_summary_service import build_clinical_summary, MISSING_AUTO


def test_extract_renal_hepatic_and_46():
    out = build_clinical_summary(
        {
            "4.1": "Indicado para X",
            "4.2": "En insuficiencia renal moderada ajustar dosis. En insuficiencia hepática leve vigilar.",
            "4.3": "Contraindicado en hipersensibilidad.",
            "4.4": "Advertencias generales.",
            "4.6": "Durante el embarazo valorar riesgo beneficio. Compatible con lactancia con precaución.",
        },
        has_nregistro=True,
        has_cima_ok=True,
    )
    assert "insuficiencia renal" in out["resumen_ajuste_renal"].lower()
    assert "insuficiencia hepática" in out["resumen_ajuste_hepatico"].lower()
    assert "embarazo" in (out["resumen_embarazo"] or "").lower()
    assert "lactancia" in (out["resumen_lactancia"] or "").lower()
    assert out["resumen_general"]


def test_missing_renal_returns_default_and_warning():
    out = build_clinical_summary({"4.2": "Posología estándar", "4.4": "Advertencias"}, True, True)
    assert out["resumen_ajuste_renal"] == MISSING_AUTO
    assert any("sin coincidencias renal" in w for w in out["warnings_json"])


def test_resumen_general_only_41_and_no_missing_placeholder():
    out = build_clinical_summary({"4.1": "Indicado para dolor agudo."}, True, True)
    assert out["resumen_general"] is not None
    assert "indicaciones" in out["resumen_general"].lower()
    assert "No localizado automáticamente" not in out["resumen_general"]


def test_resumen_general_truncates_and_warns():
    huge = "Frase clínica. " * 300
    out = build_clinical_summary({"4.1": huge, "4.2": huge, "4.3": huge, "4.4": huge, "4.6": huge}, True, True)
    assert out["resumen_general"] is not None
    assert len(out["resumen_general"]) <= 1201
    assert any("resumen_general: truncado a 1200 caracteres" == w for w in out["warnings_json"])


def test_no_sections_sets_missing_source_and_null_general():
    out = build_clinical_summary({}, True, True)
    assert out["source_status"] == "missing_source"
    assert out["resumen_general"] is None
