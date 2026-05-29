from app.services.gft_canonical_payload_service import extract_bifimed_indicaciones
from app.services.normalization_service import normalize_cn


def test_normalize_cn_tolerates_missing_and_preserves_text_shape():
    assert normalize_cn(None) == ""
    assert normalize_cn(123456) == "123456"
    assert normalize_cn(" 123456 ") == "123456"
    assert normalize_cn("00123456") == "00123456"
    assert normalize_cn("720186") == "720186"


def test_extract_bifimed_indicaciones_prefers_authorized_json_and_dedupes():
    row = {
        "indicaciones_autorizadas_json": [
            {"indicacion_autorizada": "Tratamiento de artritis reumatoide activa grave."},
            {"indicacion_autorizada": " Tratamiento de artritis reumatoide activa grave. "},
        ],
        "detalle_financiacion_json": {"indicaciones": ["No debe usarse por preferencia"]},
        "raw_data": None,
    }
    assert extract_bifimed_indicaciones(row) == [
        {
            "indicacion_autorizada": "Tratamiento de artritis reumatoide activa grave.",
            "source": "indicaciones_autorizadas_json",
        }
    ]


def test_extract_bifimed_indicaciones_falls_back_to_detail_and_raw_data():
    assert extract_bifimed_indicaciones(
        {
            "indicaciones_autorizadas_json": [],
            "detalle_financiacion_json": {"financiacion": {"indicaciones": [{"texto": "Tratamiento de psoriasis en placas moderada o grave."}]}},
            "raw_data": None,
        }
    )[0]["indicacion_autorizada"] == "Tratamiento de psoriasis en placas moderada o grave."

    assert extract_bifimed_indicaciones(
        {
            "indicaciones_autorizadas_json": None,
            "detalle_financiacion_json": {},
            "raw_data": {"datos": [{"indicacion_texto": "Prevención del rechazo en pacientes trasplantados renales."}]},
        }
    )[0]["indicacion_autorizada"] == "Prevención del rechazo en pacientes trasplantados renales."


def test_extract_bifimed_indicaciones_avoids_short_financing_flags():
    row = {
        "indicaciones_autorizadas_json": [],
        "detalle_financiacion_json": {"indicaciones": ["Si", "No", "Financiado", "No financiado"]},
        "raw_data": {"financiacion": "Financiado"},
    }
    assert extract_bifimed_indicaciones(row) == []
