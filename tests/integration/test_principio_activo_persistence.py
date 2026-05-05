from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.models.principio_activo_alias import PrincipioActivoAlias
from app.services.principio_activo_service import upsert_principios_for_cn


def test_upsert_principios_for_cn_creates_principios_aliases_and_relations(db_session):
    principios = [
        {"nombre_raw": "Paracetamol", "nombre_display": "Paracetamol", "nombre_normalizado": "paracetamol", "slug": "paracetamol", "orden": 1},
        {"nombre_raw": "Codeína", "nombre_display": "Codeína", "nombre_normalizado": "codeina", "slug": "codeina", "orden": 2},
    ]

    upsert_principios_for_cn(db_session, "123456", principios)
    db_session.commit()

    assert db_session.query(PrincipioActivo).count() == 2
    assert db_session.query(PrincipioActivoAlias).count() == 2

    relations = (
        db_session.query(MedicamentoPrincipioActivo)
        .filter(MedicamentoPrincipioActivo.cn == "123456")
        .order_by(MedicamentoPrincipioActivo.orden.asc())
        .all()
    )
    assert len(relations) == 2
    assert relations[0].orden == 1
    assert relations[1].orden == 2


def test_upsert_principios_for_cn_reuses_existing_principio(db_session):
    db_session.add(PrincipioActivo(nombre_normalizado="paracetamol", nombre_display="Paracetamol", slug="paracetamol"))
    db_session.commit()

    upsert_principios_for_cn(
        db_session,
        "222222",
        [{"nombre_raw": "Paracetamol", "nombre_display": "Paracetamol", "nombre_normalizado": "paracetamol", "slug": "paracetamol", "orden": 1}],
    )
    db_session.commit()

    assert db_session.query(PrincipioActivo).filter(PrincipioActivo.nombre_normalizado == "paracetamol").count() == 1
    assert db_session.query(MedicamentoPrincipioActivo).filter(MedicamentoPrincipioActivo.cn == "222222").count() == 1


def test_upsert_principios_for_cn_resync_does_not_duplicate_relations(db_session):
    principios = [
        {"nombre_raw": "Paracetamol", "nombre_display": "Paracetamol", "nombre_normalizado": "paracetamol", "slug": "paracetamol", "orden": 1},
        {"nombre_raw": "Codeína", "nombre_display": "Codeína", "nombre_normalizado": "codeina", "slug": "codeina", "orden": 2},
    ]

    upsert_principios_for_cn(db_session, "333333", principios)
    db_session.commit()
    upsert_principios_for_cn(db_session, "333333", principios)
    db_session.commit()

    assert db_session.query(MedicamentoPrincipioActivo).filter(MedicamentoPrincipioActivo.cn == "333333").count() == 2
    assert db_session.query(PrincipioActivoAlias).count() == 2


def test_upsert_principios_for_cn_replaces_relations_for_cn(db_session):
    upsert_principios_for_cn(
        db_session,
        "444444",
        [
            {"nombre_raw": "Paracetamol", "nombre_display": "Paracetamol", "nombre_normalizado": "paracetamol", "slug": "paracetamol", "orden": 1},
            {"nombre_raw": "Codeína", "nombre_display": "Codeína", "nombre_normalizado": "codeina", "slug": "codeina", "orden": 2},
        ],
    )
    db_session.commit()

    upsert_principios_for_cn(
        db_session,
        "444444",
        [{"nombre_raw": "Ibuprofeno", "nombre_display": "Ibuprofeno", "nombre_normalizado": "ibuprofeno", "slug": "ibuprofeno", "orden": 1}],
    )
    db_session.commit()

    rels = db_session.query(MedicamentoPrincipioActivo).filter(MedicamentoPrincipioActivo.cn == "444444").all()
    assert len(rels) == 1
    pa = db_session.get(PrincipioActivo, rels[0].principio_activo_id)
    assert pa.nombre_normalizado == "ibuprofeno"


def test_upsert_principios_for_cn_empty_list_clears_relations(db_session):
    upsert_principios_for_cn(
        db_session,
        "555555",
        [{"nombre_raw": "Paracetamol", "nombre_display": "Paracetamol", "nombre_normalizado": "paracetamol", "slug": "paracetamol", "orden": 1}],
    )
    db_session.commit()

    upsert_principios_for_cn(db_session, "555555", [])
    db_session.commit()

    assert db_session.query(MedicamentoPrincipioActivo).filter(MedicamentoPrincipioActivo.cn == "555555").count() == 0


def test_upsert_principios_for_cn_deduplicates_by_normalized_name(db_session):
    upsert_principios_for_cn(
        db_session,
        "666666",
        [
            {"nombre_raw": "PARACETAMOL", "nombre_display": "PARACETAMOL", "nombre_normalizado": "paracetamol", "slug": "paracetamol", "orden": 1},
            {"nombre_raw": "Paracetamol", "nombre_display": "Paracetamol", "nombre_normalizado": "paracetamol", "slug": "paracetamol", "orden": 2},
        ],
    )
    db_session.commit()

    assert db_session.query(MedicamentoPrincipioActivo).filter(MedicamentoPrincipioActivo.cn == "666666").count() == 1


def test_upsert_principios_for_cn_ignores_invalid_items(db_session):
    upsert_principios_for_cn(
        db_session,
        "777777",
        [
            {"nombre_raw": "x", "nombre_display": "Sin normalizar", "slug": "sin-normalizar", "orden": 1},
            {"nombre_raw": "Paracetamol", "nombre_display": "Paracetamol", "nombre_normalizado": "paracetamol", "slug": "paracetamol", "orden": 2},
        ],
    )
    db_session.commit()

    assert db_session.query(MedicamentoPrincipioActivo).filter(MedicamentoPrincipioActivo.cn == "777777").count() == 1
