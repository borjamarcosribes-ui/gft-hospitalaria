from app.services.cima_sync_service import sync_cn
from app.models.cima_medicamento_cache import CimaMedicamentoCache


class FakeOk:
    status = "ok"
    error = None
    raw_payload = {"x": 1}
    data = {
        "nregistro": "nr",
        "nombre": "N",
        "presentacion": "P",
        "forma_farmaceutica": "F",
        "forma_farmaceutica_simplificada": "FS",
        "vias_administracion_json": [],
        "atc_json": [],
        "principios_activos_json": [],
        "documentos_json": [{"tipo": 1, "url": "u1"}, {"tipo": 2, "url": "u2"}],
        "url_ficha_tecnica": "u1",
        "url_prospecto": "u2",
        "fecha_ficha_tecnica": None,
        "fecha_prospecto": None,
    }


def test_sync_cn_saves_cache(db_session, monkeypatch):
    monkeypatch.setattr('app.services.cima_sync_service.CimaClient.get_by_cn', lambda self, cn: FakeOk())
    row = sync_cn(db_session, '123456', force=True)
    assert row.sync_status == 'ok'
    assert row.url_ficha_tecnica == 'u1'


def test_sync_cn_force_false_uses_cache(db_session, monkeypatch):
    db_session.add(CimaMedicamentoCache(cn='123456', sync_status='ok', nombre='cached'))
    db_session.commit()
    called = {"v": False}
    def _call(self, cn):
        called['v'] = True
        return FakeOk()
    monkeypatch.setattr('app.services.cima_sync_service.CimaClient.get_by_cn', _call)
    row = sync_cn(db_session, '123456', force=False)
    assert row.nombre == 'cached'
    assert called['v'] is False


class FakeNotFound:
    status = "not_found"
    error = None
    raw_payload = {}
    data = None


def test_sync_cn_not_found_persists(db_session, monkeypatch):
    monkeypatch.setattr('app.services.cima_sync_service.CimaClient.get_by_cn', lambda self, cn: FakeNotFound())
    row = sync_cn(db_session, '999999', force=True)
    assert row.sync_status == "not_found"
