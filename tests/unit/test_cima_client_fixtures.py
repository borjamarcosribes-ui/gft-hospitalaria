import json
from datetime import date
from pathlib import Path

from app.services.cima_client import CimaClient
from app.services.principio_activo_service import extract_principios_from_cima_data


FIXTURES_DIR = Path("tests/fixtures/cima")


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_medicamento_simple_fixture_maps_expected_fields():
    fixture = _load_fixture("medicamento_simple.json")
    mapped = CimaClient()._map_medicamento(fixture)

    assert mapped["nombre"] == "Medicamento Simple 500 mg comprimidos"
    assert mapped["nregistro"] == "12345"
    assert mapped["forma_farmaceutica"] == "Comprimido"
    assert mapped["atc_json"]
    assert mapped["principios_activos_json"]


def test_medicamento_docs_tipo_1_2_fixture_maps_docs_and_dates():
    fixture = _load_fixture("medicamento_docs_tipo_1_2.json")
    mapped = CimaClient()._map_medicamento(fixture)

    assert mapped["url_ficha_tecnica"] == "https://cima.aemps.es/docs/ft/24680/FT_24680.pdf"
    assert mapped["url_prospecto"] == "https://cima.aemps.es/docs/p/24680/P_24680.pdf"
    assert mapped["fecha_ficha_tecnica"] == date(2024, 12, 1)
    assert mapped["fecha_prospecto"] == date(2024, 12, 2)
    tipos = {d.get("tipo") for d in mapped["documentos_json"]}
    assert 1 in tipos
    assert 2 in tipos


def test_medicamento_combinacion_fixture_keeps_multiple_principios_and_normalizes():
    fixture = _load_fixture("medicamento_combinacion_principios.json")
    mapped = CimaClient()._map_medicamento(fixture)

    assert isinstance(mapped["principios_activos_json"], list)
    assert len(mapped["principios_activos_json"]) >= 2

    principios = extract_principios_from_cima_data(mapped)
    assert len(principios) >= 2
