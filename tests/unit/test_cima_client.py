import httpx
from app.services.cima_client import CimaClient


class MockResp:
    def __init__(self, code, payload):
        self.status_code = code
        self._payload = payload
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)
    def json(self):
        return self._payload


def test_cima_ok(monkeypatch):
    payload = {"resultados": [{"nombre": "MED", "docs": [{"tipo": 1, "url": "u1"}, {"tipo": 2, "url": "u2"}]}]}
    monkeypatch.setattr(httpx.Client, "get", lambda *a, **k: MockResp(200, payload))
    r = CimaClient().get_by_cn("123")
    assert r.status == "ok"
    assert r.data["url_ficha_tecnica"] == "u1"
    assert r.data["url_prospecto"] == "u2"


def test_cima_not_found(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", lambda *a, **k: MockResp(200, {"resultados": []}))
    r = CimaClient().get_by_cn("123")
    assert r.status == "not_found"


def test_cima_timeout(monkeypatch):
    def _raise(*a, **k):
        raise httpx.TimeoutException("t")
    monkeypatch.setattr(httpx.Client, "get", _raise)
    r = CimaClient().get_by_cn("123")
    assert r.status == "error"


def test_cima_extract_dates(monkeypatch):
    payload = {"docs": [{"tipo": 1, "url": "u1", "fecha": "2024-01-02"}, {"tipo": 2, "url": "u2", "fecha": "2024-03-04"}] }
    monkeypatch.setattr(httpx.Client, "get", lambda *a, **k: MockResp(200, payload))
    r = CimaClient().get_by_cn("123")
    assert r.data["fecha_ficha_tecnica"].isoformat() == "2024-01-02"
    assert r.data["fecha_prospecto"].isoformat() == "2024-03-04"
