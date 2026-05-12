import json
from pathlib import Path

import httpx

from app.services.cima_segmented_client import CimaSegmentedClient

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "cima_segmented"


def load_json(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def load_text(name: str):
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class MockResp:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._payload


def test_get_sections_ok(monkeypatch):
    def _get(*args, **kwargs):
        assert kwargs["headers"] == {"Accept": "application/json"}
        assert kwargs["params"] == {"nregistro": "70030"}
        return MockResp(200, load_json("sections_ok.json"))

    monkeypatch.setattr(httpx.Client, "get", _get)

    result = CimaSegmentedClient(base_url="https://example.test/cima").get_sections("70030")

    assert result.status == "ok"
    assert result.data["nregistro"] == "70030"
    assert result.data["tipo_documento"] == 1
    assert any(section["seccion"] == "4.1" for section in result.data["secciones"])


def test_get_sections_error_payload_maps_to_not_segmented(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "get",
        lambda *args, **kwargs: MockResp(200, load_json("content_section_unavailable.json")),
    )

    result = CimaSegmentedClient(base_url="https://example.test/cima").get_sections("70030")

    assert result.status == "not_segmented"
    assert result.raw_payload == load_json("content_section_unavailable.json")


def test_get_section_content_ok(monkeypatch):
    responses = iter([
        MockResp(200, load_json("content_4_1.json")),
        MockResp(200, text=load_text("content_4_1.txt")),
    ])

    def _get(*args, **kwargs):
        assert kwargs["params"] == {"nregistro": "70030", "seccion": "4.1"}
        return next(responses)

    monkeypatch.setattr(httpx.Client, "get", _get)

    result = CimaSegmentedClient(base_url="https://example.test/cima").get_section_content("70030")

    assert result.status == "ok"
    assert result.data["contenido_html"] == "<div><p>Tratamiento sintomático de la fiebre y del dolor leve a moderado.</p></div>"
    assert result.data["contenido_texto"] == "Tratamiento sintomático de la fiebre y del dolor leve a moderado."
    assert result.raw_payload["text"] == load_text("content_4_1.txt")


def test_get_section_content_error_payload_maps_to_section_unavailable(monkeypatch):
    monkeypatch.setattr(
        httpx.Client,
        "get",
        lambda *args, **kwargs: MockResp(200, load_json("content_section_unavailable.json")),
    )

    result = CimaSegmentedClient(base_url="https://example.test/cima").get_section_content("70030", seccion="9.9")

    assert result.status == "section_unavailable"
    assert result.raw_payload == {"json": load_json("content_section_unavailable.json")}


def test_get_section_content_text_failure_keeps_json_ok(monkeypatch):
    calls = {"count": 0}

    def _get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return MockResp(200, load_json("content_4_1.json"))
        raise httpx.ConnectError("text unavailable")

    monkeypatch.setattr(httpx.Client, "get", _get)

    result = CimaSegmentedClient(base_url="https://example.test/cima").get_section_content("70030")

    assert result.status == "ok"
    assert result.data["contenido_texto"] is None
    assert "text_error" in result.raw_payload


def test_timeout_returns_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx.Client, "get", _raise)

    result = CimaSegmentedClient(base_url="https://example.test/cima").get_sections("70030")

    assert result.status == "error"
    assert result.error == "timeout"
