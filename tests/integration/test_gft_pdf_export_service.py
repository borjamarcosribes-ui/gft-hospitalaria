from dataclasses import asdict
import uuid

from sqlalchemy import text

from app.models.bifimed_cache import BifimedCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.services.gft_pdf_export_service import build_gft_pdf_export_data, extract_bifimed_indicaciones_from_cache
from app.services.gft_pdf_html_render_service import render_gft_pdf_html


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
              g.ajuste_insuficiencia_renal,
              g.ajuste_insuficiencia_hepatica,
              g.precauciones_embarazo,
              g.precauciones_lactancia,
              g.observaciones_publicables
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


def _insert_medicamento(
    db_session,
    cn: str,
    *,
    estado_gft: str = "incluido",
    estado_editorial: str = "publicado",
    nombre: str | None = None,
    principio_activo: str | None = "Paracetamol",
    forma_farmaceutica: str | None = "Comprimido",
    vias_administracion_json=None,
    atc_json=None,
    nemonico: str | None = None,
    restricciones_hospitalarias: str | None = "Uso hospitalario",
    ajuste_insuficiencia_renal: str | None = "Ajuste renal",
    ajuste_insuficiencia_hepatica: str | None = "Ajuste hepático",
    precauciones_embarazo: str | None = "Precaución embarazo",
    precauciones_lactancia: str | None = "Precaución lactancia",
    situacion_financiacion: str | None = "Financiado",
):
    db_session.add(
        GFTEstadoPresentacion(
            cn=cn,
            estado_gft=estado_gft,
            estado_editorial=estado_editorial,
            nemonico=nemonico if nemonico is not None else f"NEM-{cn}",
            restricciones_hospitalarias=restricciones_hospitalarias,
            ajuste_insuficiencia_renal=ajuste_insuficiencia_renal,
            ajuste_insuficiencia_hepatica=ajuste_insuficiencia_hepatica,
            precauciones_embarazo=precauciones_embarazo,
            precauciones_lactancia=precauciones_lactancia,
            observaciones_internas="Observación interna no exportable",
            observaciones_publicables="Observación publicable exportable",
            comentario_revision="Comentario no exportable",
            revisado_por="revisor no exportable",
        )
    )
    db_session.add(
        CimaMedicamentoCache(
            cn=cn,
            nregistro=f"NR{cn}",
            nombre=nombre if nombre is not None else f"Nombre {cn}",
            presentacion=f"Presentación {cn}",
            forma_farmaceutica=forma_farmaceutica,
            forma_farmaceutica_simplificada="comprimido",
            vias_administracion_json=vias_administracion_json
            if vias_administracion_json is not None
            else [{"nombre": "Vía oral"}],
            atc_json=atc_json if atc_json is not None else [{"codigo": "A01AA01", "nombre": "ATC test", "nivel": "L5"}],
            principios_activos_json=[{"nombre": principio_activo}] if principio_activo else [],
            documentos_json=[{"tipo": 1, "url": "https://example.com/doc"}],
            url_ficha_tecnica=f"https://example.com/ft/{cn}" if cn != "900001" else "",
            url_prospecto=f"https://example.com/pr/{cn}",
            raw_data={"not": "exportable"},
            sync_status="ok",
            sync_error="No exportable",
        )
    )
    if situacion_financiacion is not None:
        db_session.add(
            BifimedCache(
                cn=cn,
                situacion_financiacion=situacion_financiacion,
                raw_data={"not": "exportable"},
                sync_status="ok",
                sync_error="No exportable",
            )
        )
    if principio_activo:
        principio_activo_nombre = f"{principio_activo} {cn}"
        principio = PrincipioActivo(
            id=uuid.uuid4(),
            nombre_normalizado=principio_activo_nombre.lower(),
            nombre_display=principio_activo_nombre,
            slug=f"{principio_activo.lower().replace(' ', '-')}-{cn}",
        )
        db_session.add(principio)
        db_session.flush()
        db_session.add(MedicamentoPrincipioActivo(cn=cn, principio_activo_id=principio.id, orden=1))
    db_session.commit()


def _update_bifimed_cache(db_session, cn: str, **values):
    row = db_session.get(BifimedCache, cn)
    assert row is not None
    for key, value in values.items():
        setattr(row, key, value)
    db_session.commit()


def _add_indicaciones_cache(db_session, cn: str, contenido_texto: str):
    db_session.add(
        CimaFichaTecnicaCache(
            cn=cn,
            nregistro=f"NR{cn}",
            tipo_documento=1,
            seccion="4.1",
            titulo="Indicaciones terapéuticas",
            contenido_html="<p>No exportable</p>",
            contenido_texto=contenido_texto,
            raw_data={"not": "exportable"},
            sync_status="ok",
        )
    )
    db_session.commit()


def _all_medicamentos(export_data):
    medicamentos = []
    for group in export_data.groups:
        medicamentos.extend(group.medicamentos)
        for child in group.children:
            medicamentos.extend(child.medicamentos)
    return medicamentos


def test_gft_pdf_export_only_includes_published_medicamentos(db_session):
    _insert_medicamento(db_session, "100001")
    _insert_medicamento(db_session, "100002", estado_gft="excluido")
    _insert_medicamento(db_session, "100003", estado_editorial="pendiente")
    _insert_medicamento(db_session, "100004", estado_editorial="borrador")
    _insert_medicamento(db_session, "100005", estado_gft="retirado")
    _create_view(db_session)

    export_data = build_gft_pdf_export_data(db_session)

    assert [med.cn for med in _all_medicamentos(export_data)] == ["100001"]
    assert export_data.total_medicamentos == 1


def test_gft_pdf_export_sorts_deterministically(db_session):
    _insert_medicamento(
        db_session,
        "200003",
        nombre="Zeta",
        principio_activo="Zolpidem",
        atc_json=[{"codigo": "N05CF02", "nombre": "Zolpidem", "nivel": "L5"}],
    )
    _insert_medicamento(
        db_session,
        "200001",
        nombre="Alfa",
        principio_activo="Metformina",
        atc_json=[{"codigo": "A10BA02", "nombre": "Metformina", "nivel": "L5"}],
    )
    _insert_medicamento(
        db_session,
        "200002",
        nombre="Beta",
        principio_activo="Paracetamol",
        atc_json=[{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}],
    )
    _create_view(db_session)

    export_data = build_gft_pdf_export_data(db_session)

    assert [med.cn for med in _all_medicamentos(export_data)] == ["200001", "200002", "200003"]


def test_gft_pdf_export_groups_by_atc_l1_l2_when_available(db_session):
    _insert_medicamento(
        db_session,
        "300001",
        atc_json=[{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}],
    )
    _insert_medicamento(
        db_session,
        "300002",
        atc_json=[{"codigo": "N05CF02", "nombre": "Zolpidem", "nivel": "L5"}],
    )
    _create_view(db_session)

    export_data = build_gft_pdf_export_data(db_session)

    assert [group.codigo for group in export_data.groups] == ["N"]
    n_group = export_data.groups[0]
    assert n_group.nivel == "L1"
    assert n_group.count == 2
    assert [child.codigo for child in n_group.children] == ["N02", "N05"]
    assert [child.nivel for child in n_group.children] == ["L2", "L2"]
    assert [child.count for child in n_group.children] == [1, 1]


def test_gft_pdf_export_uses_no_informado_for_empty_fields(db_session):
    _insert_medicamento(
        db_session,
        "900001",
        principio_activo=None,
        forma_farmaceutica=None,
        vias_administracion_json=[],
        atc_json=[],
        nemonico="",
        restricciones_hospitalarias=None,
        ajuste_insuficiencia_renal=None,
        ajuste_insuficiencia_hepatica="",
        precauciones_embarazo=None,
        precauciones_lactancia="",
        situacion_financiacion=None,
    )
    _create_view(db_session)

    medication = _all_medicamentos(build_gft_pdf_export_data(db_session))[0]

    assert medication.principio_activo == "No informado"
    assert medication.forma_farmaceutica == "No informado"
    assert medication.via_administracion == "No informado"
    assert medication.nemonico == "No informado"
    assert medication.codigo_atc == "No informado"
    assert medication.descripcion_atc == "No informado"
    assert medication.ajuste_insuficiencia_renal == "No informado"
    assert medication.ajuste_insuficiencia_hepatica == "No informado"
    assert medication.precauciones_embarazo == "No informado"
    assert medication.precauciones_lactancia == "No informado"
    assert medication.restricciones_hospitalarias == "No informado"
    assert medication.situacion_financiacion_bifimed == "No informado"
    assert medication.url_ficha_tecnica == "No informado"


def test_gft_pdf_export_assigns_real_principio_activo_from_relation(db_session):
    _insert_medicamento(db_session, "610001", principio_activo="Adalimumab")
    _create_view(db_session)

    medication = _all_medicamentos(build_gft_pdf_export_data(db_session, mode="narrative"))[0]

    assert medication.principio_activo == "Adalimumab 610001"


def test_gft_pdf_export_falls_back_to_public_row_principios_activos_json(db_session):
    _insert_medicamento(db_session, "610002", principio_activo="Misoprostol")
    db_session.query(MedicamentoPrincipioActivo).filter(MedicamentoPrincipioActivo.cn == "610002").delete()
    db_session.commit()
    _create_view(db_session)

    medication = _all_medicamentos(build_gft_pdf_export_data(db_session, mode="narrative"))[0]

    assert medication.principio_activo == "Misoprostol"


def test_gft_pdf_export_matches_principio_activo_with_normalized_cn(db_session):
    _insert_medicamento(db_session, "610003", principio_activo="Sirolimus")
    association = (
        db_session.query(MedicamentoPrincipioActivo)
        .filter(MedicamentoPrincipioActivo.cn == "610003")
        .one()
    )
    association.cn = " 610003 "
    db_session.commit()
    _create_view(db_session)

    medication = _all_medicamentos(build_gft_pdf_export_data(db_session, mode="narrative"))[0]

    assert medication.principio_activo == "Sirolimus 610003"


def test_gft_pdf_export_includes_indicaciones_ficha_tecnica(db_session):
    _insert_medicamento(db_session, "400001")
    _add_indicaciones_cache(db_session, "400001", "Indicación pública para PDF")
    _create_view(db_session)

    medication = _all_medicamentos(build_gft_pdf_export_data(db_session, mode="full"))[0]

    assert medication.indicaciones_ficha_tecnica == "Indicación pública para PDF"


def test_gft_pdf_export_table_omits_long_fields(db_session):
    _insert_medicamento(db_session, "400002")
    _add_indicaciones_cache(db_session, "400002", "Indicación pública para PDF")
    _create_view(db_session)

    medication = _all_medicamentos(build_gft_pdf_export_data(db_session, mode="table"))[0]
    assert medication.indicaciones_ficha_tecnica == ""
    assert medication.ajuste_insuficiencia_renal == ""


def test_gft_pdf_export_loads_resumen_clinico_from_cache(db_session):
    _insert_medicamento(db_session, "400003")
    db_session.add(
        GftClinicalSummaryCache(
            cn="400003",
            source_status="ok",
            resumen_ajuste_renal="Ajuste renal automático",
            resumen_ajuste_hepatico="Ajuste hepático automático",
            resumen_embarazo="Embarazo automático",
            resumen_lactancia="Lactancia automática",
        )
    )
    db_session.commit()
    _create_view(db_session)

    medication = _all_medicamentos(build_gft_pdf_export_data(db_session, mode="narrative"))[0]
    assert medication.resumen_clinico_auto is not None
    assert medication.resumen_clinico_auto["ajuste_renal"] == "Ajuste renal automático"
    assert medication.resumen_clinico_auto["ajuste_hepatico"] == "Ajuste hepático automático"


def test_gft_pdf_export_serializable_structure_excludes_internal_technical_fields(db_session):
    _insert_medicamento(db_session, "500001")
    _add_indicaciones_cache(db_session, "500001", "Indicación exportable")
    _create_view(db_session)

    payload = asdict(build_gft_pdf_export_data(db_session))
    payload_text = str(payload)

    forbidden_fields = [
        "raw_data",
        "contenido_html",
        "sync_status",
        "sync_error",
        "comentario_revision",
        "revisado_por",
        "fecha_revision",
        "observaciones_internas",
        "estado_gft",
        "estado_editorial",
    ]
    for field in forbidden_fields:
        assert field not in payload_text


def test_gft_pdf_export_total_matches_structured_medicamentos(db_session):
    _insert_medicamento(db_session, "600001")
    _insert_medicamento(db_session, "600002", atc_json=[{"codigo": "B01AA03", "nombre": "Warfarina", "nivel": "L5"}])
    _create_view(db_session)

    export_data = build_gft_pdf_export_data(db_session)

    assert export_data.total_medicamentos == len(_all_medicamentos(export_data)) == 2


def test_gft_pdf_export_renders_required_bifimed_field_without_cache_and_no_fake_indications(db_session):
    _insert_medicamento(db_session, "600030", principio_activo=None, situacion_financiacion=None)
    _create_view(db_session)

    export_data = build_gft_pdf_export_data(db_session, mode="narrative")
    medication = _all_medicamentos(export_data)[0]
    html = render_gft_pdf_html(export_data)

    assert medication.indicaciones_bifimed == []
    assert medication.principio_activo == "No informado"
    assert medication.situacion_financiacion_bifimed == "No informado"
    assert "Principio activo:" in html
    assert "Financiación BIFIMED:" in html
    assert "No informado" in html
    assert "Indicaciones BIFIMED:" not in html


def test_extract_bifimed_indicaciones_uses_indicaciones_autorizadas_json():
    row = BifimedCache(
        cn="600001",
        situacion_financiacion="Financiada",
        indicaciones_autorizadas_json=[
            {"indicacion_autorizada": "Tratamiento autorizado completo desde campo normalizado"}
        ],
        detalle_financiacion_json={"indicaciones": ["Tratamiento duplicado en detalle que no debe importar"]},
        raw_data={"indicaciones": ["Tratamiento duplicado en raw que no debe importar"]},
        sync_status="ok",
    )

    indicaciones = extract_bifimed_indicaciones_from_cache(row)

    assert indicaciones == [
        {
            "indicacion_autorizada": "Tratamiento autorizado completo desde campo normalizado",
            "situacion_financiacion": "Financiada",
            "origen": "indicaciones_autorizadas_json",
        }
    ]


def test_gft_pdf_export_extracts_bifimed_indicaciones_from_detalle_and_renders_them(db_session):
    _insert_medicamento(db_session, "600002")
    _update_bifimed_cache(
        db_session,
        "600002",
        indicaciones_autorizadas_json=[],
        detalle_financiacion_json={
            "indicaciones": [
                {"indicacion_autorizada": "Tratamiento BIFIMED completo extraído desde detalle financiación"}
            ]
        },
        raw_data={},
    )
    _create_view(db_session)

    export_data = build_gft_pdf_export_data(db_session, mode="narrative")
    medication = _all_medicamentos(export_data)[0]
    html = render_gft_pdf_html(export_data)

    assert medication.indicaciones_bifimed[0]["origen"] == "detalle_financiacion_json"
    assert "Tratamiento BIFIMED completo extraído desde detalle financiación" in html


def test_gft_pdf_export_extracts_bifimed_indicaciones_from_raw_data_and_renders_them(db_session):
    _insert_medicamento(db_session, "600003")
    _update_bifimed_cache(
        db_session,
        "600003",
        indicaciones_autorizadas_json=None,
        detalle_financiacion_json={},
        raw_data={
            "respuesta": {
                "indicacion_texto": "Tratamiento BIFIMED completo extraído desde raw data para pacientes concretos"
            }
        },
    )
    _create_view(db_session)

    export_data = build_gft_pdf_export_data(db_session, mode="narrative")
    medication = _all_medicamentos(export_data)[0]
    html = render_gft_pdf_html(export_data)

    assert medication.indicaciones_bifimed[0]["origen"] == "raw_data"
    assert "Tratamiento BIFIMED completo extraído desde raw data para pacientes concretos" in html


def test_gft_pdf_export_assigns_bifimed_indicaciones_to_multiple_distinct_cns(db_session):
    _insert_medicamento(db_session, "600011", nombre="Medicamento A")
    _insert_medicamento(db_session, "600012", nombre="Medicamento B")
    _insert_medicamento(db_session, "600013", nombre="Medicamento C")
    _update_bifimed_cache(
        db_session,
        "600011",
        detalle_financiacion_json={"indicaciones": ["Tratamiento autorizado completo para medicamento A"]},
    )
    _update_bifimed_cache(
        db_session,
        "600012",
        raw_data={"indicacion_autorizada": "Tratamiento autorizado completo para medicamento B"},
    )
    _update_bifimed_cache(
        db_session,
        "600013",
        detalle_financiacion_json={
            "bloques": [{"texto": "Condiciones de financiación completas para medicamento C"}]
        },
    )
    _create_view(db_session)

    medications_by_cn = {med.cn: med for med in _all_medicamentos(build_gft_pdf_export_data(db_session))}

    assert medications_by_cn["600011"].indicaciones_bifimed[0]["indicacion_autorizada"] == (
        "Tratamiento autorizado completo para medicamento A"
    )
    assert medications_by_cn["600012"].indicaciones_bifimed[0]["indicacion_autorizada"] == (
        "Tratamiento autorizado completo para medicamento B"
    )
    assert medications_by_cn["600013"].indicaciones_bifimed[0]["indicacion_autorizada"] == (
        "Condiciones de financiación completas para medicamento C"
    )


def test_extract_bifimed_indicaciones_deduplicates_and_rejects_false_positives():
    row = BifimedCache(
        cn="600020",
        situacion_financiacion="Financiada",
        indicaciones_autorizadas_json=[],
        detalle_financiacion_json={
            "indicaciones": ["Tratamiento autorizado completo duplicado para deduplicar"]
        },
        raw_data={
            "financiado": "Si",
            "financiacion": "No financiado",
            "indicacion": "Tratamiento autorizado completo duplicado para deduplicar",
        },
        sync_status="ok",
    )

    indicaciones = extract_bifimed_indicaciones_from_cache(row)

    assert indicaciones == [
        {
            "indicacion_autorizada": "Tratamiento autorizado completo duplicado para deduplicar",
            "situacion_financiacion": "Financiada",
            "origen": "detalle_financiacion_json",
        }
    ]


def test_extract_bifimed_indicaciones_rejects_raw_data_with_only_financing_flags():
    row = BifimedCache(
        cn="600021",
        situacion_financiacion="Financiada",
        indicaciones_autorizadas_json=[],
        detalle_financiacion_json={},
        raw_data={"financiado": "Si", "financiacion": "No financiado", "estado": "Financiado"},
        sync_status="ok",
    )

    assert extract_bifimed_indicaciones_from_cache(row) == []
