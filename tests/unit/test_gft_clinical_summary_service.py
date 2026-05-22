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


def test_missing_renal_returns_default_and_warning():
    out = build_clinical_summary({"4.2": "Posología estándar", "4.4": "Advertencias"}, True, True)
    assert out["resumen_ajuste_renal"] == MISSING_AUTO
    assert any("sin coincidencias renal" in w for w in out["warnings_json"])
