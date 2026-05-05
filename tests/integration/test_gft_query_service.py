import uuid

from sqlalchemy import text

from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.services.gft_query_service import get_medicamento_by_cn, list_medicamentos


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
