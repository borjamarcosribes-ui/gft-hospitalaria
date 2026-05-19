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


def test_map_medicamento_coerces_text_fields_from_dicts():
    client = CimaClient()
    med = {
        "nombre": {"nombre": "Medicamento X"},
        "presentacion": {"descripcion": "Caja con 10"},
        "formaFarmaceutica": {"id": 288, "nombre": "POLVO PARA SOLUCIÓN INYECTABLE Y PARA PERFUSIÓN"},
        "formaFarmaceuticaSimplificada": {"id": 34, "nombre": "INYECTABLE"},
        "docs": [
            {"tipo": 1, "url": {"codigo": "https://example.com/ft"}},
            {"tipo": 2, "urlHtml": {"descripcion": "https://example.com/pr"}},
        ],
    }

    mapped = client._map_medicamento(med)

    assert mapped["nombre"] == "Medicamento X"
    assert mapped["presentacion"] == "Caja con 10"
    assert mapped["forma_farmaceutica"] == "POLVO PARA SOLUCIÓN INYECTABLE Y PARA PERFUSIÓN"
    assert mapped["forma_farmaceutica_simplificada"] == "INYECTABLE"
    assert mapped["url_ficha_tecnica"] == "https://example.com/ft"
    assert mapped["url_prospecto"] == "https://example.com/pr"


def test_map_medicamento_does_not_emit_dict_in_text_fields():
    client = CimaClient()
    med = {
        "nombre": ["unexpected"],
        "presentacion": {"id": 10},
        "formaFarmaceutica": {"id": 1},
        "formaFarmaceuticaSimplificada": {"otro": "x"},
    }

    mapped = client._map_medicamento(med)

    assert mapped["nombre"] is None
    assert mapped["presentacion"] is None
    assert mapped["forma_farmaceutica"] is None
    assert mapped["forma_farmaceutica_simplificada"] is None
