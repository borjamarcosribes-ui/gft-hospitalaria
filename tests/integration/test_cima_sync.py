import uuid

from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging
from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.models.principio_activo_alias import PrincipioActivoAlias
from app.services.cima_sync_service import sync_cn, sync_import_batch


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


class FakeNotFound:
    status = "not_found"
    error = None
    raw_payload = {}
    data = None


class FakeError:
    status = "error"
    error = "boom"
    raw_payload = {}
    data = None


def test_sync_cn_saves_cache(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.cima_sync_service.CimaClient.get_by_cn",
        lambda self, cn: FakeOk(),
    )
    row = sync_cn(db_session, "123456", force=True)
    assert row.sync_status == "ok"
    assert row.url_ficha_tecnica == "u1"


def test_sync_cn_force_false_uses_cache(db_session, monkeypatch):
    db_session.add(CimaMedicamentoCache(cn="123456", sync_status="ok", nombre="cached"))
    db_session.commit()

    called = {"v": False}

    def _call(self, cn):
        called["v"] = True
        return FakeOk()

    monkeypatch.setattr("app.services.cima_sync_service.CimaClient.get_by_cn", _call)

    row = sync_cn(db_session, "123456", force=False)

    assert row.nombre == "cached"
    assert called["v"] is False


def test_sync_cn_not_found_persists(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.cima_sync_service.CimaClient.get_by_cn",
        lambda self, cn: FakeNotFound(),
    )
    row = sync_cn(db_session, "999999", force=True)
    assert row.sync_status == "not_found"


def test_sync_import_batch_filters_and_counts(db_session, monkeypatch):
    batch = ImportBatch(filename="x.xlsx", status="validated")
    db_session.add(batch)
    db_session.flush()

    db_session.add_all(
        [
            ImportRowStaging(
                id=uuid.uuid4(),
                batch_id=batch.id,
                row_number=1,
                cn_normalized="111111",
                estado_gft="incluido",
                estado_editorial="publicado",
                validation_errors=[],
            ),
            ImportRowStaging(
                id=uuid.uuid4(),
                batch_id=batch.id,
                row_number=2,
                cn_normalized="111111",
                estado_gft="incluido",
                estado_editorial="publicado",
                validation_errors=[],
            ),
            ImportRowStaging(
                id=uuid.uuid4(),
                batch_id=batch.id,
                row_number=3,
                cn_normalized="222222",
                estado_gft="incluido",
                estado_editorial="publicado",
                validation_errors=[],
            ),
            ImportRowStaging(
                id=uuid.uuid4(),
                batch_id=batch.id,
                row_number=4,
                cn_normalized="333333",
                estado_gft="incluido",
                estado_editorial="publicado",
                validation_errors=[],
            ),
            ImportRowStaging(
                id=uuid.uuid4(),
                batch_id=batch.id,
                row_number=5,
                cn_normalized="444444",
                estado_gft="excluido",
                estado_editorial="publicado",
                validation_errors=[],
            ),
            ImportRowStaging(
                id=uuid.uuid4(),
                batch_id=batch.id,
                row_number=6,
                cn_normalized="555555",
                estado_gft="incluido",
                estado_editorial="publicado",
                validation_errors=["err"],
            ),
        ]
    )
    db_session.commit()

    def fake_get(self, cn):
        if cn == "111111":
            return FakeOk()
        if cn == "222222":
            return FakeNotFound()
        return FakeError()

    monkeypatch.setattr("app.services.cima_sync_service.CimaClient.get_by_cn", fake_get)

    res = sync_import_batch(db_session, batch.id, force=True)

    assert res["total_cn"] == 3
    assert res["ok"] == 1
    assert res["not_found"] == 1
    assert res["error"] == 1


def test_sync_cn_ok_persists_principios_relationally(db_session, monkeypatch):
    class FakeOkPrincipios(FakeOk):
        data = {
            **FakeOk.data,
            "principios_activos_json": [
                {"nombre": "Paracetamol"},
                {"nombre": "Codeína"},
            ],
        }

    monkeypatch.setattr(
        "app.services.cima_sync_service.CimaClient.get_by_cn",
        lambda self, cn: FakeOkPrincipios(),
    )

    row = sync_cn(db_session, "123456", force=True)

    rels = db_session.query(MedicamentoPrincipioActivo).filter_by(cn="123456").order_by(MedicamentoPrincipioActivo.orden).all()
    assert row.sync_status == "ok"
    assert db_session.query(PrincipioActivo).count() == 2
    assert db_session.query(PrincipioActivoAlias).count() == 2
    assert len(rels) == 2
    assert [r.orden for r in rels] == [1, 2]


def test_sync_cn_ok_empty_principios_clears_previous_relations(db_session, monkeypatch):
    class FakeOkWithPrincipios(FakeOk):
        data = {**FakeOk.data, "principios_activos_json": [{"nombre": "Paracetamol"}]}

    monkeypatch.setattr(
        "app.services.cima_sync_service.CimaClient.get_by_cn",
        lambda self, cn: FakeOkWithPrincipios(),
    )
    sync_cn(db_session, "123456", force=True)
    assert db_session.query(MedicamentoPrincipioActivo).filter_by(cn="123456").count() == 1

    class FakeOkEmptyPrincipios(FakeOk):
        data = {**FakeOk.data, "principios_activos_json": []}

    monkeypatch.setattr(
        "app.services.cima_sync_service.CimaClient.get_by_cn",
        lambda self, cn: FakeOkEmptyPrincipios(),
    )
    sync_cn(db_session, "123456", force=True)

    assert db_session.query(MedicamentoPrincipioActivo).filter_by(cn="123456").count() == 0


def test_sync_cn_not_found_does_not_clear_existing_principios(db_session, monkeypatch):
    class FakeOkWithPrincipios(FakeOk):
        data = {**FakeOk.data, "principios_activos_json": [{"nombre": "Paracetamol"}]}

    monkeypatch.setattr("app.services.cima_sync_service.CimaClient.get_by_cn", lambda self, cn: FakeOkWithPrincipios())
    sync_cn(db_session, "123456", force=True)

    monkeypatch.setattr("app.services.cima_sync_service.CimaClient.get_by_cn", lambda self, cn: FakeNotFound())
    row = sync_cn(db_session, "123456", force=True)

    assert row.sync_status == "not_found"
    assert db_session.query(MedicamentoPrincipioActivo).filter_by(cn="123456").count() == 1


def test_sync_cn_error_does_not_clear_existing_principios(db_session, monkeypatch):
    class FakeOkWithPrincipios(FakeOk):
        data = {**FakeOk.data, "principios_activos_json": [{"nombre": "Paracetamol"}]}

    monkeypatch.setattr("app.services.cima_sync_service.CimaClient.get_by_cn", lambda self, cn: FakeOkWithPrincipios())
    sync_cn(db_session, "123456", force=True)

    monkeypatch.setattr("app.services.cima_sync_service.CimaClient.get_by_cn", lambda self, cn: FakeError())
    row = sync_cn(db_session, "123456", force=True)

    assert row.sync_status == "error"
    assert db_session.query(MedicamentoPrincipioActivo).filter_by(cn="123456").count() == 1


def test_sync_import_batch_persists_principios_via_sync_cn(db_session, monkeypatch):
    batch = ImportBatch(filename="x.xlsx", status="validated")
    db_session.add(batch)
    db_session.flush()
    db_session.add(
        ImportRowStaging(
            id=uuid.uuid4(),
            batch_id=batch.id,
            row_number=1,
            cn_normalized="123456",
            estado_gft="incluido",
            estado_editorial="publicado",
            validation_errors=[],
        )
    )
    db_session.commit()

    class FakeOkPrincipios(FakeOk):
        data = {**FakeOk.data, "principios_activos_json": [{"nombre": "Paracetamol"}]}

    monkeypatch.setattr("app.services.cima_sync_service.CimaClient.get_by_cn", lambda self, cn: FakeOkPrincipios())

    result = sync_import_batch(db_session, batch.id, force=True)

    assert result["ok"] == 1
    assert db_session.query(MedicamentoPrincipioActivo).filter_by(cn="123456").count() == 1
