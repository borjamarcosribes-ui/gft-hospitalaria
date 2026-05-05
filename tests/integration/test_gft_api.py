import uuid

from sqlalchemy import text

from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo


def _create_view(db_session):
    db_session.execute(text("DROP VIEW IF EXISTS v_gft_publicada"))
    db_session.execute(
        text(
            """
            CREATE VIEW v_gft_publicada AS
            SELECT
              g.cn,
              g.nemonico,
              c.nombre,
              c.presentacion,
              c.forma_farmaceutica,
              c.forma_farmaceutica_simplificada,
              c.vias_administracion_json,
              c.atc_json,
              c.principios_activos_json,
              c.documentos_json,
              c.url_ficha_tecnica,
              c.url_prospecto,
              NULL AS situacion_financiacion,
              g.restricciones_hospitalarias,
              g.observaciones_internas
            FROM gft_estado_presentacion g
            LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
            WHERE g.estado_gft = 'incluido'
              AND g.estado_editorial = 'publicado'
            """
        )
    )
    db_session.commit()


def _insert_base_medicamento(db_session, cn: str, publicado: bool = True):
    db_session.add(
        GFTEstadoPresentacion(
            cn=cn,
            estado_gft="incluido",
            estado_editorial="publicado" if publicado else "borrador",
            nemonico=f"NEM-{cn}",
            restricciones_hospitalarias="Uso hospitalario",
            observaciones_internas="Observación interna",
        )
    )
    db_session.add(
        CimaMedicamentoCache(
            cn=cn,
            nombre=f"Nombre {cn}",
            presentacion=f"Presentación {cn}",
            forma_farmaceutica="Comprimido",
            vias_administracion_json=[{"nombre": "Vía oral"}],
            atc_json=[{"codigo": "A01AA01", "nombre": "ATC test", "nivel": "L5"}],
            principios_activos_json=[{"nombre": "Paracetamol"}],
            documentos_json=[{"tipo": 1, "url": "https://example.com/doc"}],
            url_ficha_tecnica=f"https://example.com/ft/{cn}",
            url_prospecto=f"https://example.com/pr/{cn}",
            sync_status="ok",
        )
    )
    db_session.commit()


def test_gft_list_medicamentos_endpoint(client, db_session):
    _insert_base_medicamento(db_session, "123456", publicado=True)
    _insert_base_medicamento(db_session, "654321", publicado=False)
    _create_view(db_session)

    response = client.get("/gft/medicamentos")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["cn"] == "123456"


def test_gft_list_medicamentos_pagination_params(client, db_session):
    for cn in ("400001", "400002", "400003"):
        _insert_base_medicamento(db_session, cn, publicado=True)
    _create_view(db_session)

    response = client.get("/gft/medicamentos?limit=2&offset=1")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2


def test_gft_get_medicamento_detail_endpoint(client, db_session):
    _insert_base_medicamento(db_session, "111111", publicado=True)
    _create_view(db_session)

    response = client.get("/gft/medicamentos/111111")

    assert response.status_code == 200
    body = response.json()
    assert body["cn"] == "111111"
    assert body["nombre"] == "Nombre 111111"
    assert body["url_ficha_tecnica"] == "https://example.com/ft/111111"
    assert body["url_prospecto"] == "https://example.com/pr/111111"
    assert isinstance(body["documentos"], list)
    assert body["documentos"]


def test_gft_get_medicamento_detail_404(client, db_session):
    _create_view(db_session)
    response = client.get("/gft/medicamentos/999999")

    assert response.status_code == 404


def test_gft_api_does_not_expose_raw_data(client, db_session):
    _insert_base_medicamento(db_session, "555555", publicado=True)
    _create_view(db_session)

    list_response = client.get("/gft/medicamentos")
    detail_response = client.get("/gft/medicamentos/555555")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert "raw_data" not in list_response.json()["items"][0]
    assert "raw_data" not in detail_response.json()


def test_gft_list_medicamentos_q_param(client, db_session):
    _insert_base_medicamento(db_session, "910001", publicado=True)
    _insert_base_medicamento(db_session, "910002", publicado=True)
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Aspirina infantil' WHERE cn='910001'"))
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Vitamina C' WHERE cn='910002'"))
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/medicamentos?q=aspiri")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["cn"] == "910001"


def test_gft_list_medicamentos_letra_param(client, db_session):
    _insert_base_medicamento(db_session, "920001", publicado=True)
    _insert_base_medicamento(db_session, "920002", publicado=True)
    pa_paracetamol = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="paracetamol", nombre_display="Paracetamol", slug="paracetamol")
    pa_ibuprofeno = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="ibuprofeno", nombre_display="Ibuprofeno", slug="ibuprofeno")
    db_session.add_all([pa_paracetamol, pa_ibuprofeno])
    db_session.flush()
    db_session.add_all(
        [
            MedicamentoPrincipioActivo(cn="920001", principio_activo_id=pa_paracetamol.id, orden=1),
            MedicamentoPrincipioActivo(cn="920002", principio_activo_id=pa_ibuprofeno.id, orden=1),
        ]
    )
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/medicamentos?letra=P")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["cn"] == "920001"


def test_gft_list_medicamentos_principio_activo_param(client, db_session):
    _insert_base_medicamento(db_session, "930001", publicado=True)
    _insert_base_medicamento(db_session, "930002", publicado=True)
    pa_paracetamol = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="paracetamol", nombre_display="Paracetamol", slug="paracetamol")
    pa_ibuprofeno = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="ibuprofeno", nombre_display="Ibuprofeno", slug="ibuprofeno")
    db_session.add_all([pa_paracetamol, pa_ibuprofeno])
    db_session.flush()
    db_session.add_all(
        [
            MedicamentoPrincipioActivo(cn="930001", principio_activo_id=pa_paracetamol.id, orden=1),
            MedicamentoPrincipioActivo(cn="930002", principio_activo_id=pa_ibuprofeno.id, orden=1),
        ]
    )
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/medicamentos?principio_activo=ibuprofeno")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["cn"] == "930002"
