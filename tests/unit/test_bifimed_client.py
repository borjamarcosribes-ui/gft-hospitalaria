from pathlib import Path

import httpx

from app.services.bifimed_client import BifimedClient


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "bifimed"


class MockResp:
    def __init__(self, code: int, text: str = ""):
        self.status_code = code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)


def _load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_get_by_cn_ok_with_simple_fixture(monkeypatch):
    def _get(self, url, params):
        assert params == {"cn": "988220", "metodo": "verDetalle"}
        return MockResp(200, _load_fixture("detail_ok_simple.html"))

    monkeypatch.setattr(httpx.Client, "get", _get)

    result = BifimedClient(base_url="https://example.test/medicamentos.do").get_by_cn("988220")

    assert result.status == "ok"
    assert result.data["situacion_financiacion"] == "Si"
    assert result.data["detalle_financiacion_json"]["Código nacional"] == "988220"
    assert result.raw_payload == {"html": _load_fixture("detail_ok_simple.html")}


def test_get_by_cn_ok_with_invalid_detail_returns_not_found(monkeypatch):
    html = "<html><body><p>Sin ficha válida</p></body></html>"
    monkeypatch.setattr(httpx.Client, "get", lambda *a, **k: MockResp(200, html))

    result = BifimedClient(base_url="https://example.test/medicamentos.do").get_by_cn("988220")

    assert result.status == "not_found"
    assert result.raw_payload == {"html": html}


def test_get_by_cn_404_returns_not_found(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", lambda *a, **k: MockResp(404))

    result = BifimedClient(base_url="https://example.test/medicamentos.do").get_by_cn("988220")

    assert result.status == "not_found"
    assert result.data is None
    assert result.error is None


def test_get_by_cn_timeout_returns_error_timeout(monkeypatch):
    def _raise(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx.Client, "get", _raise)

    result = BifimedClient(base_url="https://example.test/medicamentos.do").get_by_cn("988220")

    assert result.status == "error"
    assert result.error == "timeout"
