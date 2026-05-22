from datetime import date
from datetime import datetime
import uuid

from sqlalchemy import text

from app.models.bifimed_cache import BifimedCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.services.gft_query_service import (
    get_medicamento_by_cn,
    list_atc_index,
    list_medicamentos,
    list_principios_activos_index,
)


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
              g.restricciones_hospitalarias,
              g.observaciones_internas
            FROM gft_estado_presentacion g
            LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
            LEFT JOIN bifimed_cache b ON b.cn = g.cn
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


def test_list_medicamentos_returns_only_view_rows(db_session):
    _insert_base_medicamento(db_session, "123456", publicado=True)
    _insert_base_medicamento(db_session, "654321", publicado=False)
    _create_view(db_session)

    result = list_medicamentos(db_session)

    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["cn"] == "123456"


def test_get_medicamento_by_cn_returns_detail(db_session):
    _insert_base_medicamento(db_session, "111111", publicado=True)
    _create_view(db_session)

    result = get_medicamento_by_cn(db_session, "111111")

    assert result is not None
    assert result["cn"] == "111111"
    assert result["nombre"] == "Nombre 111111"
    assert result["url_ficha_tecnica"] == "https://example.com/ft/111111"
    assert result["url_prospecto"] == "https://example.com/pr/111111"
    assert isinstance(result["documentos"], list)
    assert result["documentos"]


def test_get_medicamento_by_cn_includes_detail_metadata(db_session):
    _insert_base_medicamento(db_session, "111112", publicado=True)
    medicamento = db_session.get(CimaMedicamentoCache, "111112")
    assert medicamento is not None
    medicamento.fecha_ficha_tecnica = date(2024, 1, 2)
    medicamento.fecha_prospecto = date(2024, 2, 3)
    db_session.commit()
    _create_view(db_session)

    result = get_medicamento_by_cn(db_session, "111112")

    assert result is not None
    assert result["forma_farmaceutica_simplificada"] == "comprimido"
    assert str(result["fecha_ficha_tecnica"]) == "2024-01-02"
    assert str(result["fecha_prospecto"]) == "2024-02-03"


def test_get_medicamento_by_cn_includes_financiacion_detalle_when_available(db_session):
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

    result = get_medicamento_by_cn(db_session, "111113")

    assert result is not None
    assert result["situacion_financiacion"] == "Financiado"
    assert result["financiacion_detalle"] == {
        "situacion_financiacion": "Financiado",
        "condiciones_financiacion_restringidas": "Diagnóstico hospitalario",
        "condiciones_especiales_financiacion": "Visado",
        "estado_nomenclator": "Alta",
        "aportacion_usuario": "Reducida",
        "subgrupo_atc": "N02BE",
    }


def test_get_medicamento_by_cn_includes_bifimed_last_synced_at_when_available(db_session):
    _insert_base_medicamento(db_session, "111115", publicado=True)
    synced_at = datetime(2026, 5, 22, 10, 30)
    db_session.add(
        BifimedCache(
            cn="111115",
            situacion_financiacion="Financiado",
            condiciones_financiacion_restringidas="Uso controlado",
            condiciones_especiales_financiacion="Visado",
            estado_nomenclator="Alta",
            aportacion_usuario="Normal",
            subgrupo_atc="N02BE",
            last_synced_at=synced_at,
            sync_status="ok",
        )
    )
    db_session.commit()
    _create_view(db_session)

    result = get_medicamento_by_cn(db_session, "111115")

    assert result is not None
    assert result["financiacion_detalle"] is not None
    assert result["financiacion_detalle"]["last_synced_at"] == synced_at


def test_get_medicamento_by_cn_documents_are_typed_shape(db_session):
    _insert_base_medicamento(db_session, "111114", publicado=True)
    medicamento = db_session.get(CimaMedicamentoCache, "111114")
    assert medicamento is not None
    medicamento.documentos_json = [
        {
            "tipo": 1,
            "url": "https://example.com/ft.pdf",
            "urlHtml": "https://example.com/ft.html",
            "secc": "4.1",
            "fecha": "2024-01-02",
            "titulo": "Ficha técnica",
            "nombre": "Documento FT",
            "extra": "no expuesto",
        }
    ]
    db_session.commit()
    _create_view(db_session)

    result = get_medicamento_by_cn(db_session, "111114")

    assert result is not None
    assert result["documentos"] == [
        {
            "tipo": 1,
            "url": "https://example.com/ft.pdf",
            "urlHtml": "https://example.com/ft.html",
            "secc": "4.1",
            "fecha": "2024-01-02",
            "titulo": "Ficha técnica",
            "nombre": "Documento FT",
        }
    ]


def test_get_medicamento_by_cn_returns_none_when_not_in_view(db_session):
    _insert_base_medicamento(db_session, "222222", publicado=False)
    _create_view(db_session)

    result = get_medicamento_by_cn(db_session, "222222")

    assert result is None


def test_list_medicamentos_includes_relational_principios(db_session):
    _insert_base_medicamento(db_session, "333333", publicado=True)

    pa = PrincipioActivo(
        id=uuid.uuid4(),
        nombre_normalizado="paracetamol",
        nombre_display="Paracetamol",
        slug="paracetamol",
    )
    db_session.add(pa)
    db_session.flush()
    db_session.add(
        MedicamentoPrincipioActivo(
            cn="333333",
            principio_activo_id=pa.id,
            orden=1,
        )
    )
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session)

    principios = result["items"][0]["principios_activos"]
    assert principios
    assert principios[0]["nombre"] == "Paracetamol"
    assert principios[0]["slug"] == "paracetamol"


def test_list_medicamentos_pagination(db_session):
    for cn in ("400001", "400002", "400003"):
        _insert_base_medicamento(db_session, cn, publicado=True)
    _create_view(db_session)

    page = list_medicamentos(db_session, limit=2, offset=1)

    assert page["total"] == 3
    assert page["limit"] == 2
    assert page["offset"] == 1
    assert len(page["items"]) == 2


def test_responses_do_not_expose_raw_data(db_session):
    _insert_base_medicamento(db_session, "555555", publicado=True)
    _create_view(db_session)

    listed = list_medicamentos(db_session)
    detail = get_medicamento_by_cn(db_session, "555555")

    assert "raw_data" not in listed["items"][0]
    assert detail is not None
    assert "raw_data" not in detail


def test_list_medicamentos_pagination_applies_after_sorting(db_session):
    _insert_base_medicamento(db_session, "700001", publicado=True)
    _insert_base_medicamento(db_session, "700002", publicado=True)
    _insert_base_medicamento(db_session, "700003", publicado=True)

    pa_z = PrincipioActivo(
        id=uuid.uuid4(),
        nombre_normalizado="zeta",
        nombre_display="Zeta",
        slug="zeta",
    )
    pa_a = PrincipioActivo(
        id=uuid.uuid4(),
        nombre_normalizado="alfa",
        nombre_display="Alfa",
        slug="alfa",
    )
    pa_m = PrincipioActivo(
        id=uuid.uuid4(),
        nombre_normalizado="mu",
        nombre_display="Mu",
        slug="mu",
    )
    db_session.add_all([pa_z, pa_a, pa_m])
    db_session.flush()

    db_session.add_all(
        [
            MedicamentoPrincipioActivo(cn="700001", principio_activo_id=pa_z.id, orden=1),
            MedicamentoPrincipioActivo(cn="700002", principio_activo_id=pa_a.id, orden=1),
            MedicamentoPrincipioActivo(cn="700003", principio_activo_id=pa_m.id, orden=1),
        ]
    )
    db_session.commit()
    _create_view(db_session)

    first_page = list_medicamentos(db_session, limit=1, offset=0)
    second_page = list_medicamentos(db_session, limit=1, offset=1)

    assert first_page["items"][0]["cn"] == "700002"  # Alfa
    assert second_page["items"][0]["cn"] == "700003"  # Mu


def test_list_medicamentos_filter_q_by_nombre(db_session):
    _insert_base_medicamento(db_session, "800001", publicado=True)
    _insert_base_medicamento(db_session, "800002", publicado=True)
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Dalsy pediátrico' WHERE cn='800002'"))
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session, q="dalsy")
    assert result["total"] == 1
    assert result["items"][0]["cn"] == "800002"


def test_list_medicamentos_filter_q_by_principio_activo(db_session):
    _insert_base_medicamento(db_session, "810001", publicado=True)
    _insert_base_medicamento(db_session, "810002", publicado=True)
    pa_paracetamol = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="paracetamol", nombre_display="Paracetamol", slug="paracetamol")
    pa_ibuprofeno = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="ibuprofeno", nombre_display="Ibuprofeno", slug="ibuprofeno")
    db_session.add_all([pa_paracetamol, pa_ibuprofeno])
    db_session.flush()
    db_session.add_all(
        [
            MedicamentoPrincipioActivo(cn="810001", principio_activo_id=pa_paracetamol.id, orden=1),
            MedicamentoPrincipioActivo(cn="810002", principio_activo_id=pa_ibuprofeno.id, orden=1),
        ]
    )
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session, q="ibupr")
    assert result["total"] == 1
    assert result["items"][0]["cn"] == "810002"


def test_list_medicamentos_filter_letra(db_session):
    _insert_base_medicamento(db_session, "820001", publicado=True)
    _insert_base_medicamento(db_session, "820002", publicado=True)
    pa_paracetamol = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="paracetamol", nombre_display="Paracetamol", slug="paracetamol")
    pa_ibuprofeno = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="ibuprofeno", nombre_display="Ibuprofeno", slug="ibuprofeno")
    db_session.add_all([pa_paracetamol, pa_ibuprofeno])
    db_session.flush()
    db_session.add_all(
        [
            MedicamentoPrincipioActivo(cn="820001", principio_activo_id=pa_paracetamol.id, orden=1),
            MedicamentoPrincipioActivo(cn="820002", principio_activo_id=pa_ibuprofeno.id, orden=1),
        ]
    )
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session, letra="P")
    assert result["total"] == 1
    assert result["items"][0]["cn"] == "820001"


def test_list_medicamentos_filter_principio_activo_by_slug(db_session):
    _insert_base_medicamento(db_session, "830001", publicado=True)
    _insert_base_medicamento(db_session, "830002", publicado=True)
    pa_paracetamol = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="paracetamol", nombre_display="Paracetamol", slug="paracetamol")
    pa_ibuprofeno = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="ibuprofeno", nombre_display="Ibuprofeno", slug="ibuprofeno")
    db_session.add_all([pa_paracetamol, pa_ibuprofeno])
    db_session.flush()
    db_session.add_all(
        [
            MedicamentoPrincipioActivo(cn="830001", principio_activo_id=pa_paracetamol.id, orden=1),
            MedicamentoPrincipioActivo(cn="830002", principio_activo_id=pa_ibuprofeno.id, orden=1),
        ]
    )
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session, principio_activo="IBUPROFENO")
    assert result["total"] == 1
    assert result["items"][0]["cn"] == "830002"


def test_list_medicamentos_filter_principio_activo_by_id(db_session):
    _insert_base_medicamento(db_session, "840001", publicado=True)
    _insert_base_medicamento(db_session, "840002", publicado=True)
    pa_paracetamol = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="paracetamol", nombre_display="Paracetamol", slug="paracetamol")
    pa_ibuprofeno = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="ibuprofeno", nombre_display="Ibuprofeno", slug="ibuprofeno")
    db_session.add_all([pa_paracetamol, pa_ibuprofeno])
    db_session.flush()
    db_session.add_all(
        [
            MedicamentoPrincipioActivo(cn="840001", principio_activo_id=pa_paracetamol.id, orden=1),
            MedicamentoPrincipioActivo(cn="840002", principio_activo_id=pa_ibuprofeno.id, orden=1),
        ]
    )
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session, principio_activo=str(pa_paracetamol.id))
    assert result["total"] == 1
    assert result["items"][0]["cn"] == "840001"


def test_list_medicamentos_filters_before_pagination(db_session):
    _insert_base_medicamento(db_session, "850001", publicado=True)
    _insert_base_medicamento(db_session, "850002", publicado=True)
    _insert_base_medicamento(db_session, "850003", publicado=True)
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Filtro X uno' WHERE cn='850001'"))
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Filtro X dos' WHERE cn='850002'"))
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Sin coincidencia' WHERE cn='850003'"))
    db_session.commit()
    _create_view(db_session)

    page = list_medicamentos(db_session, q="filtro x", limit=1, offset=1)
    assert page["total"] == 2
    assert page["limit"] == 1
    assert page["offset"] == 1
    assert len(page["items"]) == 1


def _set_atc_json(db_session, cn: str, atc_json):
    medicamento = db_session.get(CimaMedicamentoCache, cn)
    assert medicamento is not None
    medicamento.atc_json = atc_json


def test_list_medicamentos_filter_atc_exact_or_full_prefix(db_session):
    _insert_base_medicamento(db_session, "860001", publicado=True)
    _insert_base_medicamento(db_session, "860002", publicado=True)
    _set_atc_json(db_session, "860001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "860002", [{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}])
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session, atc="N02BE01")

    assert result["total"] == 1
    assert result["items"][0]["cn"] == "860001"


def test_list_medicamentos_filter_atc_prefix(db_session):
    _insert_base_medicamento(db_session, "861001", publicado=True)
    _insert_base_medicamento(db_session, "861002", publicado=True)
    _insert_base_medicamento(db_session, "861003", publicado=True)
    _set_atc_json(db_session, "861001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "861002", [{"codigo": "N02AX02", "nombre": "Tramadol", "nivel": "L5"}])
    _set_atc_json(db_session, "861003", [{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}])
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session, atc="N02")

    assert result["total"] == 2
    assert {item["cn"] for item in result["items"]} == {"861001", "861002"}


def test_list_medicamentos_filter_atc_case_insensitive_and_strip(db_session):
    _insert_base_medicamento(db_session, "862001", publicado=True)
    _insert_base_medicamento(db_session, "862002", publicado=True)
    _set_atc_json(db_session, "862001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "862002", [{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}])
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session, atc=" n02be ")

    assert result["total"] == 1
    assert result["items"][0]["cn"] == "862001"


def test_list_medicamentos_filter_atc_combines_with_q_before_pagination(db_session):
    _insert_base_medicamento(db_session, "863001", publicado=True)
    _insert_base_medicamento(db_session, "863002", publicado=True)
    _insert_base_medicamento(db_session, "863003", publicado=True)
    _set_atc_json(db_session, "863001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "863002", [{"codigo": "N02AX02", "nombre": "Tramadol", "nivel": "L5"}])
    _set_atc_json(db_session, "863003", [{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}])
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Dolor Diana' WHERE cn='863001'"))
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Analgesico sin texto' WHERE cn='863002'"))
    db_session.execute(text("UPDATE cima_medicamento_cache SET nombre='Dolor Diana fuera' WHERE cn='863003'"))
    db_session.commit()
    _create_view(db_session)

    page = list_medicamentos(db_session, atc="N02", q="diana", limit=1, offset=0)

    assert page["total"] == 1
    assert page["limit"] == 1
    assert page["offset"] == 0
    assert len(page["items"]) == 1
    assert page["items"][0]["cn"] == "863001"


def test_list_medicamentos_filter_atc_ignores_missing_or_invalid_atc(db_session):
    _insert_base_medicamento(db_session, "864001", publicado=True)
    _insert_base_medicamento(db_session, "864002", publicado=True)
    _insert_base_medicamento(db_session, "864003", publicado=True)
    _insert_base_medicamento(db_session, "864004", publicado=True)
    _set_atc_json(db_session, "864001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "864002", None)
    _set_atc_json(db_session, "864003", "not-json")
    _set_atc_json(db_session, "864004", {"codigo": "N02AX02"})
    db_session.commit()
    _create_view(db_session)

    result = list_medicamentos(db_session, atc="N02")

    assert result["total"] == 1
    assert result["items"][0]["cn"] == "864001"



def test_list_atc_index_returns_present_codes_with_counts(db_session):
    _insert_base_medicamento(db_session, "870001", publicado=True)
    _insert_base_medicamento(db_session, "870002", publicado=True)
    _insert_base_medicamento(db_session, "870003", publicado=True)
    _set_atc_json(db_session, "870001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    _set_atc_json(db_session, "870002", [{"codigo": "N02AX02", "nombre": "Tramadol", "nivel": "L5"}])
    _set_atc_json(db_session, "870003", [{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}])
    db_session.commit()
    _create_view(db_session)

    result = list_atc_index(db_session)
    items_by_code = {item["codigo"]: item for item in result["items"]}

    for codigo in {"N", "N02", "N02B", "N02BE01", "N02AX02", "A", "A10", "A10BA02"}:
        assert codigo in items_by_code
    assert items_by_code["N"]["count"] == 2
    assert items_by_code["N02"]["count"] == 2
    assert items_by_code["A"]["count"] == 1
    assert [item["codigo"] for item in result["items"]] == sorted(items_by_code)


def test_list_atc_index_deduplicates_same_cn_same_prefix(db_session):
    _insert_base_medicamento(db_session, "871001", publicado=True)
    _set_atc_json(
        db_session,
        "871001",
        [
            {"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"},
            {"codigo": "N02AX02", "nombre": "Tramadol", "nivel": "L5"},
        ],
    )
    db_session.commit()
    _create_view(db_session)

    result = list_atc_index(db_session)
    items_by_code = {item["codigo"]: item for item in result["items"]}

    assert items_by_code["N"]["count"] == 1
    assert items_by_code["N02"]["count"] == 1


def test_list_atc_index_uses_name_only_for_exact_payload_code(db_session):
    _insert_base_medicamento(db_session, "872001", publicado=True)
    _set_atc_json(db_session, "872001", [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}])
    db_session.commit()
    _create_view(db_session)

    result = list_atc_index(db_session)
    items_by_code = {item["codigo"]: item for item in result["items"]}

    assert items_by_code["N02BE01"]["nombre"] == "Paracetamol"
    for codigo in ("N", "N02", "N02B", "N02BE"):
        assert items_by_code[codigo]["nombre"] is None


def test_list_atc_index_ignores_invalid_or_missing_atc(db_session):
    _insert_base_medicamento(db_session, "873001", publicado=True)
    _insert_base_medicamento(db_session, "873002", publicado=True)
    _insert_base_medicamento(db_session, "873003", publicado=True)
    _set_atc_json(db_session, "873001", None)
    _set_atc_json(db_session, "873002", "not-json")
    _set_atc_json(db_session, "873003", {"codigo": "N02AX02"})
    db_session.commit()
    _create_view(db_session)

    result = list_atc_index(db_session)

    assert result == {"items": []}


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


def test_list_principios_activos_index_returns_only_published_principios(db_session):
    _insert_base_medicamento(db_session, "950001", publicado=True)
    _insert_base_medicamento(db_session, "950002", publicado=True)
    _insert_base_medicamento(db_session, "950003", publicado=False)
    _add_principio_relacion(db_session, "950001", "Paracetamol", "paracetamol")
    _add_principio_relacion(db_session, "950002", "Ibuprofeno", "ibuprofeno")
    _add_principio_relacion(db_session, "950003", "Metformina", "metformina")
    db_session.commit()
    _create_view(db_session)

    result = list_principios_activos_index(db_session)

    slugs = {item["slug"] for item in result["items"]}
    assert slugs == {"ibuprofeno", "paracetamol"}


def test_list_principios_activos_index_counts_unique_cns(db_session):
    _insert_base_medicamento(db_session, "951001", publicado=True)
    _insert_base_medicamento(db_session, "951002", publicado=True)
    principio = _add_principio_relacion(db_session, "951001", "Paracetamol", "paracetamol")
    db_session.add(MedicamentoPrincipioActivo(cn="951002", principio_activo_id=principio.id, orden=1))
    db_session.commit()
    _create_view(db_session)

    result = list_principios_activos_index(db_session)

    assert result["items"] == [
        {
            "id": principio.id,
            "slug": "paracetamol",
            "nombre": "Paracetamol",
            "letra": "P",
            "count": 2,
        }
    ]


def test_list_principios_activos_index_deduplicates_same_cn_same_principio(db_session):
    _insert_base_medicamento(db_session, "952001", publicado=True)
    principio = _add_principio_relacion(db_session, "952001", "Paracetamol", "paracetamol")
    db_session.commit()
    # The relation table primary key prevents duplicate CN/principio rows, so the
    # view is duplicated to exercise the service-level CN set deduplication.
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
              g.restricciones_hospitalarias,
              g.observaciones_internas
            FROM gft_estado_presentacion g
            LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
            LEFT JOIN bifimed_cache b ON b.cn = g.cn
            WHERE g.cn = '952001'
            UNION ALL
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
              g.restricciones_hospitalarias,
              g.observaciones_internas
            FROM gft_estado_presentacion g
            LEFT JOIN cima_medicamento_cache c ON c.cn = g.cn
            LEFT JOIN bifimed_cache b ON b.cn = g.cn
            WHERE g.cn = '952001'
            """
        )
    )
    db_session.commit()

    result = list_principios_activos_index(db_session)

    assert result["items"][0]["id"] == principio.id
    assert result["items"][0]["count"] == 1


def test_list_principios_activos_index_letra_and_order(db_session):
    _insert_base_medicamento(db_session, "953001", publicado=True)
    _insert_base_medicamento(db_session, "953002", publicado=True)
    _add_principio_relacion(db_session, "953001", "Paracetamol", "paracetamol")
    _add_principio_relacion(db_session, "953002", "Ibuprofeno", "ibuprofeno")
    db_session.commit()
    _create_view(db_session)

    result = list_principios_activos_index(db_session)

    assert [(item["nombre"], item["letra"]) for item in result["items"]] == [
        ("Ibuprofeno", "I"),
        ("Paracetamol", "P"),
    ]


def test_list_principios_activos_index_empty_when_no_publicados(db_session):
    _insert_base_medicamento(db_session, "954001", publicado=False)
    _add_principio_relacion(db_session, "954001", "Paracetamol", "paracetamol")
    db_session.commit()
    _create_view(db_session)

    result = list_principios_activos_index(db_session)

    assert result == {"items": []}
