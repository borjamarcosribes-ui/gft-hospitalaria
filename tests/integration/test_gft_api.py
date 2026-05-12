from datetime import date
import uuid

from sqlalchemy import text

from app.models.bifimed_cache import BifimedCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
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
              c.fecha_ficha_tecnica,
              c.fecha_prospecto,
              b.situacion_financiacion,
              b.condiciones_financiacion_restringidas,
              b.condiciones_especiales_financiacion,
              b.estado_nomenclator,
              b.aportacion_usuario,
              b.subgrupo_atc,
              ft41.contenido_texto AS indicaciones_ficha_tecnica,
              g.restricciones_hospitalarias,
              g.observaciones_internas
            FROM gft_estado_presentacion g
            LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
            LEFT JOIN bifimed_cache b ON b.cn = g.cn
            LEFT JOIN cima_ficha_tecnica_cache ft41
              ON ft41.nregistro = c.nregistro
             AND ft41.tipo_documento = 1
             AND ft41.seccion = '4.1'
             AND ft41.sync_status = 'ok'
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
            nregistro=f"NR{cn}",
            nombre=f"Nombre {cn}",
            presentacion=f"Presentación {cn}",
            forma_farmaceutica="Comprimido",
            forma_farmaceutica_simplificada="comprimido",
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


def _add_indicaciones_cache(
    db_session,
    cn: str,
    contenido_texto: str = "Indicación FT test",
    sync_status: str = "ok",
):
    db_session.add(
        CimaFichaTecnicaCache(
            cn=cn,
            nregistro=f"NR{cn}",
            tipo_documento=1,
            seccion="4.1",
            titulo="Indicaciones terapéuticas",
            contenido_html="<p>No público</p>",
            contenido_texto=contenido_texto,
            raw_data={"not": "public"},
            sync_status=sync_status,
            sync_error="No público" if sync_status != "ok" else None,
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
    assert body["items"][0]["indicaciones_ficha_tecnica"] is None


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
    assert body["indicaciones_ficha_tecnica"] is None
    assert isinstance(body["documentos"], list)
    assert body["documentos"]


def test_gft_list_medicamentos_exposes_indicaciones_ficha_tecnica(client, db_session):
    _insert_base_medicamento(db_session, "777001", publicado=True)
    _add_indicaciones_cache(db_session, "777001", "Indicación pública desde FT")
    _create_view(db_session)

    response = client.get("/gft/medicamentos")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["indicaciones_ficha_tecnica"] == "Indicación pública desde FT"
    assert "contenido_html" not in body["items"][0]
    assert "raw_data" not in body["items"][0]
    assert "sync_status" not in body["items"][0]
    assert "sync_error" not in body["items"][0]


def test_gft_get_medicamento_detail_exposes_indicaciones_ficha_tecnica(client, db_session):
    _insert_base_medicamento(db_session, "777002", publicado=True)
    _add_indicaciones_cache(db_session, "777002", "Indicación detalle desde FT")
    _create_view(db_session)

    response = client.get("/gft/medicamentos/777002")

    assert response.status_code == 200
    body = response.json()
    assert body["indicaciones_ficha_tecnica"] == "Indicación detalle desde FT"
    assert "contenido_html" not in body
    assert "raw_data" not in body
    assert "sync_status" not in body
    assert "sync_error" not in body


def test_gft_indicaciones_ficha_tecnica_requires_ok_cache(client, db_session):
    _insert_base_medicamento(db_session, "777003", publicado=True)
    _add_indicaciones_cache(db_session, "777003", "No debe exponerse", sync_status="error")
    _create_view(db_session)

    list_response = client.get("/gft/medicamentos")
    detail_response = client.get("/gft/medicamentos/777003")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert list_response.json()["items"][0]["indicaciones_ficha_tecnica"] is None
    assert detail_response.json()["indicaciones_ficha_tecnica"] is None


def test_gft_get_medicamento_detail_includes_metadata(client, db_session):
    _insert_base_medicamento(db_session, "111112", publicado=True)
    medicamento = db_session.get(CimaMedicamentoCache, "111112")
    assert medicamento is not None
    medicamento.fecha_ficha_tecnica = date(2024, 1, 2)
    medicamento.fecha_prospecto = date(2024, 2, 3)
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/medicamentos/111112")

    assert response.status_code == 200
    body = response.json()
    assert body["forma_farmaceutica_simplificada"] == "comprimido"
    assert body["fecha_ficha_tecnica"] == "2024-01-02"
    assert body["fecha_prospecto"] == "2024-02-03"


def test_gft_get_medicamento_detail_includes_financiacion_detalle(client, db_session):
    _insert_base_medicamento(db_session, "111113", publicado=True)
    db_session.add(
        BifimedCache(
            cn="111113",
            situacion_financiacion="Financiado",
            condiciones_financiacion_restringidas="Diagnóstico hospitalario",
            condiciones_especiales_financiacion="Visado",
            estado_nomenclator="Alta",
            aportacion_usuario="Reducida",
            subgrupo_atc="N02BE",
            sync_status="ok",
        )
    )
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/medicamentos/111113")

    assert response.status_code == 200
    body = response.json()
    assert body["situacion_financiacion"] == "Financiado"
    assert body["financiacion_detalle"] == {
        "situacion_financiacion": "Financiado",
        "condiciones_financiacion_restringidas": "Diagnóstico hospitalario",
        "condiciones_especiales_financiacion": "Visado",
        "estado_nomenclator": "Alta",
        "aportacion_usuario": "Reducida",
        "subgrupo_atc": "N02BE",
    }


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


def _set_atc_json(db_session, cn: str, atc_json):
    medicamento = db_session.get(CimaMedicamentoCache, cn)
    assert medicamento is not None
    medicamento.atc_json = atc_json


def test_gft_list_medicamentos_atc_param(client, db_session):
    _insert_base_medicamento(db_session, "940001", publicado=True)
    _insert_base_medicamento(db_session, "940002", publicado=True)
    _insert_base_medicamento(db_session, "940003", publicado=True)
    _set_atc_json(db_session, "940001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "940002", [{"codigo": "N02AX02", "nombre": "Tramadol", "nivel": "L5"}])
    _set_atc_json(db_session, "940003", [{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}])
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/medicamentos?atc=N02")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["cn"] for item in body["items"]} == {"940001", "940002"}


def test_gft_list_medicamentos_atc_combines_with_q(client, db_session):
    _insert_base_medicamento(db_session, "941001", publicado=True)
    _insert_base_medicamento(db_session, "941002", publicado=True)
    _insert_base_medicamento(db_session, "941003", publicado=True)
    _set_atc_json(db_session, "941001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "941002", [{"codigo": "N02AX02", "nombre": "Tramadol", "nivel": "L5"}])
    _set_atc_json(db_session, "941003", [{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}])
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Dolor Diana' WHERE cn='941001'"))
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Analgesico sin texto' WHERE cn='941002'"))
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Dolor Diana fuera' WHERE cn='941003'"))
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/medicamentos?atc=N02&q=diana")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["cn"] == "941001"



def test_gft_atc_index_endpoint(client, db_session):
    _insert_base_medicamento(db_session, "942001", publicado=True)
    _insert_base_medicamento(db_session, "942002", publicado=True)
    _insert_base_medicamento(db_session, "942003", publicado=True)
    _set_atc_json(db_session, "942001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "942002", [{"codigo": "N02AX02", "nombre": "Tramadol", "nivel": "L5"}])
    _set_atc_json(db_session, "942003", [{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}])
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/atc")

    assert response.status_code == 200
    body = response.json()
    items_by_code = {item["codigo"]: item for item in body["items"]}
    assert {"N", "N02", "N02BE01", "N02AX02", "A", "A10", "A10BA02"}.issubset(items_by_code)
    assert items_by_code["N"]["count"] == 2
    assert items_by_code["N02"]["count"] == 2
    assert items_by_code["A"]["count"] == 1


def test_gft_atc_index_endpoint_ignores_unpublished(client, db_session):
    _insert_base_medicamento(db_session, "943001", publicado=True)
    _insert_base_medicamento(db_session, "943002", publicado=False)
    _set_atc_json(db_session, "943001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "943002", [{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}])
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/atc")

    assert response.status_code == 200
    body = response.json()
    codes = {item["codigo"] for item in body["items"]}
    assert "N" in codes
    assert "A" not in codes


def _add_principio_relacion(db_session, cn: str, nombre: str, slug: str | None = None):
    principio = PrincipioActivo(
        id=uuid.uuid4(),
        nombre_normalizado=(slug or nombre).lower(),
        nombre_display=nombre,
        slug=slug or nombre.lower(),
    )
    db_session.add(principio)
    db_session.flush()
    db_session.add(MedicamentoPrincipioActivo(cn=cn, principio_activo_id=principio.id, orden=1))
    return principio


def test_gft_principios_activos_index_endpoint(client, db_session):
    _insert_base_medicamento(db_session, "955001", publicado=True)
    _insert_base_medicamento(db_session, "955002", publicado=True)
    principio = _add_principio_relacion(db_session, "955001", "Paracetamol", "paracetamol")
    db_session.add(MedicamentoPrincipioActivo(cn="955002", principio_activo_id=principio.id, orden=1))
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/principios-activos")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "items": [
            {
                "id": str(principio.id),
                "slug": "paracetamol",
                "nombre": "Paracetamol",
                "letra": "P",
                "count": 2,
            }
        ]
    }


def test_gft_principios_activos_index_endpoint_ignores_unpublished(client, db_session):
    _insert_base_medicamento(db_session, "956001", publicado=True)
    _insert_base_medicamento(db_session, "956002", publicado=False)
    _add_principio_relacion(db_session, "956001", "Paracetamol", "paracetamol")
    _add_principio_relacion(db_session, "956002", "Ibuprofeno", "ibuprofeno")
    db_session.commit()
    _create_view(db_session)

    response = client.get("/gft/principios-activos")

    assert response.status_code == 200
    body = response.json()
    slugs = {item["slug"] for item in body["items"]}
    assert slugs == {"paracetamol"}
    assert "ibuprofeno" not in slugs
