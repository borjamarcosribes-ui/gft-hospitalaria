import json
from pathlib import Path

from app.services.cima_segmented_parser import (
    parse_section_content_json,
    parse_section_text,
    parse_sections_payload,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "cima_segmented"


def load_json(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_parse_sections_payload_ok_contains_4_1():
    sections = parse_sections_payload(load_json("sections_ok.json"))

    assert sections is not None
    assert {section["seccion"] for section in sections} >= {"4.1"}
    section_4_1 = next(section for section in sections if section["seccion"] == "4.1")
    assert section_4_1 == {
        "seccion": "4.1",
        "titulo": "Indicaciones terapéuticas",
        "orden": 2,
    }


def test_parse_sections_payload_error_returns_none():
    assert parse_sections_payload(load_json("content_section_unavailable.json")) is None


def test_parse_section_content_json_ok_returns_html():
    result = parse_section_content_json(load_json("content_4_1.json"), requested_section="4.1")

    assert result is not None
    assert result["seccion"] == "4.1"
    assert result["titulo"] == "Indicaciones terapéuticas"
    assert result["contenido_html"] == "<div><p>Tratamiento sintomático de la fiebre y del dolor leve a moderado.</p></div>"


def test_parse_section_content_json_error_returns_none():
    assert parse_section_content_json(load_json("content_section_unavailable.json"), requested_section="4.1") is None


def test_parse_section_content_json_other_requested_section_returns_none():
    assert parse_section_content_json(load_json("content_4_1.json"), requested_section="4.2") is None


def test_parse_section_text_normalizes_spaces_line_breaks_and_nbsp():
    text = "  Tratamiento\xa0\xa0sintomático\n\tde   la fiebre.  "

    assert parse_section_text(text) == "Tratamiento sintomático de la fiebre."
