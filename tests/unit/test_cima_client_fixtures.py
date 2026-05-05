import json
from datetime import date
from pathlib import Path

from app.services.cima_client import CimaClient
from app.services.principio_activo_service import extract_principios_from_cima_data


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "cima"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_map_medicamento_simple_fixture():
    med = _load_fixture("medicamento_simple.json")

    mapped = CimaClient()._map_medicamento(med)

    assert mapped["nombre"] == "PARACETAMOL NORMON 500 mg comprimidos"
    assert mapped["nregistro"] == "123456"
    assert mapped["forma_farmaceutica"] == "Comprimido"
    assert mapped["atc_json"]
    assert mapped["principios_activos_json"]


def test_map_medicamento_docs_tipo_1_2_fixture():
    med = _load_fixture("medicamento_docs_tipo_1_2.json")

    mapped = CimaClient()._map_medicamento(med)

    assert mapped["url_ficha_tecnica"] == "https://cima.aemps.es/cima/pdfs/ft/112233/FT_112233.pdf"
    assert mapped["url_prospecto"] == "https://cima.aemps.es/cima/pdfs/p/112233/P_112233.pdf"
    assert mapped["fecha_ficha_tecnica"] == date(2023, 12, 15)
    assert mapped["fecha_prospecto"] == date(2024, 1, 2)

    tipos_docs = {doc.get("tipo") for doc in mapped["documentos_json"]}
    assert 1 in tipos_docs
    assert 2 in tipos_docs


def test_map_medicamento_combinacion_principios_fixture():
    med = _load_fixture("medicamento_combinacion_principios.json")

    mapped = CimaClient()._map_medicamento(med)

    assert isinstance(mapped["principios_activos_json"], list)
    assert len(mapped["principios_activos_json"]) >= 2

    principios = extract_principios_from_cima_data(mapped)
    assert len(principios) >= 2
