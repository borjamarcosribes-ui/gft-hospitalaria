import uuid
from sqlalchemy import text

from app.models.bifimed_cache import BifimedCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.models.medicamento_principio_activo import MedicamentoPrincipioActivo
from app.models.principio_activo import PrincipioActivo
from app.services.gft_canonical_payload_service import audit_gft_coverage, build_gft_canonical_payload


def _create_canonical_view(db_session):
    db_session.execute(text("DROP VIEW IF EXISTS v_gft_publicada"))
    db_session.execute(
        text(
            """
            CREATE VIEW v_gft_publicada AS
            SELECT
              cn,
              nemonico,
              nombre_comercial_importado AS nombre,
              presentacion_importada AS presentacion,
              forma_farmaceutica_importada AS forma_farmaceutica,
              forma_farmaceutica_importada AS forma_farmaceutica_simplificada,
              '[{"nombre":"Vía oral"}]' AS vias_administracion_json,
              '[{"codigo":"A01AA01","nombre":"ATC test","nivel":"L5"}]' AS atc_json,
              codigo_atc_importado,
              descripcion_atc_importada,
              NULL AS principios_activos_json,
              NULL AS documentos_json,
              url_ficha_tecnica_importada AS url_ficha_tecnica,
              url_prospecto_importado AS url_prospecto,
              url_ficha_tecnica_importada,
              url_prospecto_importado,
              NULL AS fecha_ficha_tecnica,
              NULL AS fecha_prospecto,
              'Indicación CIMA completa conservada sin normalización agresiva.' AS indicaciones_ficha_tecnica,
              principio_activo_importado,
              via_administracion_importada,
              restricciones_hospitalarias,
              ajuste_insuficiencia_renal,
              ajuste_insuficiencia_hepatica,
              precauciones_embarazo,
              precauciones_lactancia,
              observaciones_internas,
              observaciones_publicables,
              estado_editorial
            FROM gft_estado_presentacion
            WHERE estado_gft = 'incluido' AND estado_editorial = 'publicado'
            """
        )
    )
    db_session.commit()


def _add_gft(db_session, cn, *, principio=None, renal="Ajustar en FG bajo", hepatic=None, embarazo=None, lactancia=None, restricciones="Uso hospitalario"):
    db_session.add(
        GFTEstadoPresentacion(
            cn=cn,
            estado_gft="incluido",
            estado_editorial="publicado",
            nemonico=f"NEM-{cn}",
            nombre_comercial_importado=f"Medicamento {cn}",
            principio_activo_importado=principio,
            presentacion_importada=f"Presentación {cn}",
            forma_farmaceutica_importada="Comprimido",
            via_administracion_importada="Oral",
            codigo_atc_importado="A01AA01",
            descripcion_atc_importada="ATC test",
            url_ficha_tecnica_importada=f"https://example.test/ft/{cn}",
            url_prospecto_importado=f"https://example.test/p/{cn}",
            restricciones_hospitalarias=restricciones,
            ajuste_insuficiencia_renal=renal,
            ajuste_insuficiencia_hepatica=hepatic,
            precauciones_embarazo=embarazo,
            precauciones_lactancia=lactancia,
        )
    )


def test_canonical_payload_resolves_principio_activo_relation_spaces_and_fallbacks(db_session):
    _add_gft(db_session, "100001", principio="Fallback ignorado")
    _add_gft(db_session, "100002", principio="Principio fallback")
    _add_gft(db_session, "100003", principio=None)
    pa = PrincipioActivo(id=uuid.uuid4(), nombre_normalizado="adalimumab", nombre_display="Adalimumab", slug="adalimumab")
    db_session.add(pa)
    db_session.flush()
    db_session.add(MedicamentoPrincipioActivo(cn=" 100001 ", principio_activo_id=pa.id, orden=1))
    db_session.commit()
    _create_canonical_view(db_session)

    relation = build_gft_canonical_payload(db_session, "100001")
    fallback = build_gft_canonical_payload(db_session, "100002")
    missing = build_gft_canonical_payload(db_session, "100003")

    assert relation["principio_activo"] == "Adalimumab"
    assert "principio_activo_from_relation" in relation["data_quality_flags"]
    assert fallback["principio_activo"] == "Principio fallback"
    assert "principio_activo_from_view_principio_activo_importado" in fallback["data_quality_flags"]
    assert missing["principio_activo"] == "No informado"
    assert "principio_activo_missing" in missing["data_quality_flags"]


def test_canonical_payload_exposes_minimums_cima_urls_and_bifimed_financing(db_session):
    _add_gft(db_session, "200001", principio="Tacrolimus")
    db_session.add(
        BifimedCache(
            cn="200001",
            situacion_financiacion="Financiado",
            condiciones_financiacion_restringidas="Diagnóstico hospitalario",
            detalle_financiacion_json={"indicaciones": [{"texto": "Profilaxis del rechazo del trasplante en pacientes adultos."}]},
            sync_status="ok",
        )
    )
    db_session.commit()
    _create_canonical_view(db_session)

    payload = build_gft_canonical_payload(db_session, "200001")

    assert payload["cn"] == "200001"
    assert payload["principio_activo"] == "Tacrolimus"
    assert payload["situacion_financiacion_bifimed"] == "Financiado"
    assert payload["indicaciones_bifimed"][0]["indicacion_autorizada"] == "Profilaxis del rechazo del trasplante en pacientes adultos."
    assert payload["url_ficha_tecnica"] == "https://example.test/ft/200001"
    assert payload["url_prospecto"] == "https://example.test/p/200001"
    assert "precauciones_embarazo" in payload["campos_faltantes"]


def test_canonical_payload_marks_missing_bifimed_cache_without_inventing_indications(db_session):
    _add_gft(db_session, "200002", principio="Misoprostol")
    db_session.commit()
    _create_canonical_view(db_session)

    payload = build_gft_canonical_payload(db_session, "200002")

    assert payload["bifimed_cache_presente"] is False
    assert payload["estado_bifimed"] == "sin_cache"
    assert payload["indicaciones_bifimed"] == []
    assert "bifimed_cache" in payload["campos_faltantes"]


def test_audit_gft_coverage_counts_available_and_missing_data(db_session):
    _add_gft(db_session, "300001", principio="Adalimumab", hepatic="Sin ajuste", embarazo="Precaución", lactancia="Precaución")
    _add_gft(db_session, "300002", principio=None, renal=None, restricciones=None)
    db_session.add(
        BifimedCache(
            cn="300001",
            situacion_financiacion="Financiado",
            raw_data={"indicaciones": [{"descripcion": "Tratamiento de artritis idiopática juvenil activa."}]},
            sync_status="ok",
        )
    )
    db_session.commit()
    _create_canonical_view(db_session)

    audit = audit_gft_coverage(db_session)
    summary = audit["summary"]

    assert summary["total_medicamentos_publicados"] == 2
    assert summary["con_principio_activo"] == 1
    assert summary["sin_principio_activo"] == 1
    assert summary["con_bifimed_cache"] == 1
    assert summary["sin_bifimed_cache"] == 1
    assert summary["con_financiacion_bifimed"] == 1
    assert summary["con_indicaciones_bifimed"] == 1
    assert summary["sin_indicaciones_bifimed"] == 1
    assert summary["con_ajuste_renal"] == 1
    assert {item["cn"] for item in audit["items"]} == {"300001", "300002"}
