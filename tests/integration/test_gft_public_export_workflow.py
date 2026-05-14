from io import BytesIO
from types import SimpleNamespace

import pandas as pd
from sqlalchemy import text

from app.api.routes import gft as gft_routes
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services.bifimed_client import BifimedFetchResult
from app.services.cima_segmented_client import CimaSegmentedFetchResult


FORBIDDEN_INTERNAL_FIELDS = [
    "raw_data",
    "sync_status",
    "sync_error",
    "comentario_revision",
    "revisado_por",
    "estado_gft",
    "estado_editorial",
]

PUBLIC_CN = "111111"
EXCLUDED_CN = "222222"
PENDING_CN = "333333"
PUBLIC_NAME = "Paracetamol Publicado E2E"
EXCLUDED_NAME = "Ibuprofeno Excluido E2E"
PENDING_NAME = "Metformina Pendiente E2E"
PUBLIC_ACTIVE_INGREDIENT = "Paracetamol"
PUBLIC_ATC_CODE = "N02BE01"
PUBLIC_INDICATIONS = "Tratamiento sintomático del dolor y la fiebre desde sección 4.1"
PUBLIC_RESTRICTIONS = "Uso restringido público E2E"
PUBLIC_RENAL_ADJUSTMENT = "Ajustar dosis en insuficiencia renal pública"
PUBLIC_HEPATIC_ADJUSTMENT = "Precaución en insuficiencia hepática pública"
PUBLIC_PREGNANCY_WARNING = "Valorar beneficio riesgo en embarazo público"
PUBLIC_LACTATION_WARNING = "Compatible con lactancia bajo criterio clínico público"
PUBLIC_OBSERVATIONS = "Observación interna publicable E2E"


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


def _make_excel(rows):
    bio = BytesIO()
    pd.DataFrame(rows).to_excel(bio, index=False)
    return bio.getvalue()


def _excel_file(rows):
    return (
        "gft-public-export-workflow.xlsx",
        _make_excel(rows),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _assert_forbidden_internal_fields_are_absent(text_value: str):
    for field in FORBIDDEN_INTERNAL_FIELDS:
        assert field not in text_value


def test_public_gft_html_and_pdf_exports_use_same_published_source(client, db_session, monkeypatch):
    upload_response = client.post(
        "/imports/excel",
        files={
            "file": _excel_file(
                [
                    {
                        "CN": PUBLIC_CN,
                        "Observaciones revisión": "SI",
                        "Estado editorial": "publicado",
                        "Nemónico": f"NEM-{PUBLIC_CN}",
                        "Restricciones hospitalarias": PUBLIC_RESTRICTIONS,
                        "Observaciones internas GFT": PUBLIC_OBSERVATIONS,
                        "Comentario revisión": "Comentario interno no publicable E2E",
                        "Revisado por": "Revisor interno no publicable E2E",
                    },
                    {
                        "CN": EXCLUDED_CN,
                        "Observaciones revisión": "NO",
                        "Estado editorial": "publicado",
                        "Nemónico": f"NEM-{EXCLUDED_CN}",
                    },
                    {
                        "CN": PENDING_CN,
                        "Observaciones revisión": "guía",
                        "Estado editorial": "pendiente",
                        "Nemónico": f"NEM-{PENDING_CN}",
                    },
                ]
            )
        },
    )

    assert upload_response.status_code == 200
    batch_id = upload_response.json()["batch_id"]

    def fake_get_by_cn(self, cn):
        if cn != PUBLIC_CN:
            raise AssertionError(f"Unexpected CIMA call for CN {cn}")
        return SimpleNamespace(
            status="ok",
            error=None,
            raw_payload={"internal": "raw_data value must not be exported"},
            data={
                "nregistro": f"NR{PUBLIC_CN}",
                "nombre": PUBLIC_NAME,
                "presentacion": f"{PUBLIC_NAME} 1 g comprimidos",
                "forma_farmaceutica": "Comprimido",
                "forma_farmaceutica_simplificada": "comprimido",
                "vias_administracion_json": [{"nombre": "Vía oral"}],
                "atc_json": [
                    {"codigo": PUBLIC_ATC_CODE, "nombre": PUBLIC_ACTIVE_INGREDIENT, "nivel": "L5"}
                ],
                "principios_activos_json": [{"nombre": PUBLIC_ACTIVE_INGREDIENT}],
                "documentos_json": [
                    {"tipo": 1, "url": f"https://example.test/ft/{PUBLIC_CN}"},
                    {"tipo": 2, "url": f"https://example.test/pr/{PUBLIC_CN}"},
                ],
                "url_ficha_tecnica": f"https://example.test/ft/{PUBLIC_CN}",
                "url_prospecto": f"https://example.test/pr/{PUBLIC_CN}",
                "fecha_ficha_tecnica": None,
                "fecha_prospecto": None,
            },
        )

    monkeypatch.setattr("app.services.cima_sync_service.CimaClient.get_by_cn", fake_get_by_cn)

    sync_response = client.post(f"/cima/sync/import-batch/{batch_id}?force=true")

    assert sync_response.status_code == 200
    assert sync_response.json()["eligible_cn"] == 1
    assert sync_response.json()["ok"] == 1
    assert sync_response.json()["skipped_excluded"] == 1
    assert sync_response.json()["skipped_pending"] == 1

    def fake_segmented_get_section_content(self, nregistro, tipo_documento=1, seccion="4.1"):
        if nregistro != f"NR{PUBLIC_CN}":
            raise AssertionError(f"Unexpected CIMA segmented call for nregistro {nregistro}")
        return CimaSegmentedFetchResult(
            status="ok",
            data={
                "nregistro": nregistro,
                "tipo_documento": tipo_documento,
                "seccion": seccion,
                "titulo": "Indicaciones terapéuticas",
                "contenido_html": f"<p>{PUBLIC_INDICATIONS}</p>",
                "contenido_texto": PUBLIC_INDICATIONS,
            },
            error=None,
            raw_payload={"internal": "raw_data value must not be exported"},
        )

    monkeypatch.setattr(
        "app.services.cima_segmented_client.CimaSegmentedClient.get_section_content",
        fake_segmented_get_section_content,
    )

    segmented_sync_response = client.post(
        f"/cima/segmented/sync/import-batch/{batch_id}?force=true"
    )

    assert segmented_sync_response.status_code == 200
    assert segmented_sync_response.json()["eligible_cn"] == 1
    assert segmented_sync_response.json()["ok"] == 1
    assert segmented_sync_response.json()["skipped_excluded"] == 1
    assert segmented_sync_response.json()["skipped_pending"] == 1

    def fake_bifimed_get_by_cn(self, cn):
        if cn != PUBLIC_CN:
            raise AssertionError(f"Unexpected BIFIMED call for CN {cn}")
        return BifimedFetchResult(
            status="ok",
            data={
                "situacion_financiacion": "Financiado E2E",
                "condiciones_financiacion_restringidas": "Visado E2E",
                "condiciones_especiales_financiacion": "Condición especial E2E",
                "estado_nomenclator": "ALTA",
                "aportacion_usuario": "NORMAL",
                "subgrupo_atc": f"{PUBLIC_ATC_CODE} - {PUBLIC_ACTIVE_INGREDIENT}",
                "detalle_financiacion_json": {"Código nacional": PUBLIC_CN},
            },
            error=None,
            raw_payload={"internal": "raw_data value must not be exported"},
        )

    monkeypatch.setattr(
        "app.services.bifimed_sync_service.BifimedClient.get_by_cn", fake_bifimed_get_by_cn
    )

    bifimed_sync_response = client.post(f"/bifimed/sync/import-batch/{batch_id}?force=true")

    assert bifimed_sync_response.status_code == 200
    assert bifimed_sync_response.json()["eligible_cn"] == 1
    assert bifimed_sync_response.json()["ok"] == 1
    assert bifimed_sync_response.json()["skipped_excluded"] == 1
    assert bifimed_sync_response.json()["skipped_pending"] == 1

    apply_response = client.post(f"/imports/{batch_id}/apply")

    assert apply_response.status_code == 200
    assert apply_response.json()["applied_rows"] == 2
    assert apply_response.json()["skipped_pending"] == 1

    public_state = db_session.get(GFTEstadoPresentacion, PUBLIC_CN)
    assert public_state is not None
    public_state.ajuste_insuficiencia_renal = PUBLIC_RENAL_ADJUSTMENT
    public_state.ajuste_insuficiencia_hepatica = PUBLIC_HEPATIC_ADJUSTMENT
    public_state.precauciones_embarazo = PUBLIC_PREGNANCY_WARNING
    public_state.precauciones_lactancia = PUBLIC_LACTATION_WARNING
    db_session.commit()

    _create_view(db_session)

    list_response = client.get("/gft/medicamentos")

    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    assert [item["cn"] for item in list_payload["items"]] == [PUBLIC_CN]
    list_item = list_payload["items"][0]
    assert list_item["nombre"] == PUBLIC_NAME
    assert list_item["principios_activos"][0]["nombre"] == PUBLIC_ACTIVE_INGREDIENT
    assert list_item["atc"][0]["codigo"] == PUBLIC_ATC_CODE
    assert list_item["indicaciones_ficha_tecnica"] == PUBLIC_INDICATIONS
    assert list_item["restricciones_hospitalarias"] == PUBLIC_RESTRICTIONS
    assert list_item["ajuste_insuficiencia_renal"] == PUBLIC_RENAL_ADJUSTMENT
    assert list_item["ajuste_insuficiencia_hepatica"] == PUBLIC_HEPATIC_ADJUSTMENT
    assert list_item["precauciones_embarazo"] == PUBLIC_PREGNANCY_WARNING
    assert list_item["precauciones_lactancia"] == PUBLIC_LACTATION_WARNING

    detail_response = client.get(f"/gft/medicamentos/{PUBLIC_CN}")

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["cn"] == PUBLIC_CN
    assert detail_payload["nombre"] == PUBLIC_NAME
    assert detail_payload["principios_activos"][0]["nombre"] == PUBLIC_ACTIVE_INGREDIENT
    assert detail_payload["atc"][0]["codigo"] == PUBLIC_ATC_CODE
    assert detail_payload["indicaciones_ficha_tecnica"] == PUBLIC_INDICATIONS
    assert detail_payload["restricciones_hospitalarias"] == PUBLIC_RESTRICTIONS
    assert detail_payload["ajuste_insuficiencia_renal"] == PUBLIC_RENAL_ADJUSTMENT
    assert detail_payload["ajuste_insuficiencia_hepatica"] == PUBLIC_HEPATIC_ADJUSTMENT
    assert detail_payload["precauciones_embarazo"] == PUBLIC_PREGNANCY_WARNING
    assert detail_payload["precauciones_lactancia"] == PUBLIC_LACTATION_WARNING
    assert detail_payload["observaciones_internas_publicables"] == PUBLIC_OBSERVATIONS
    assert detail_payload["financiacion_detalle"]["situacion_financiacion"] == "Financiado E2E"
    assert client.get(f"/gft/medicamentos/{EXCLUDED_CN}").status_code == 404
    assert client.get(f"/gft/medicamentos/{PENDING_CN}").status_code == 404

    html_response = client.get("/gft/export/html")

    assert html_response.status_code == 200
    assert "text/html" in html_response.headers["content-type"]
    html = html_response.text
    assert PUBLIC_NAME in html
    assert PUBLIC_CN in html
    assert PUBLIC_ACTIVE_INGREDIENT in html
    assert PUBLIC_ATC_CODE in html
    assert PUBLIC_INDICATIONS in html
    assert PUBLIC_RESTRICTIONS in html
    assert PUBLIC_RENAL_ADJUSTMENT in html
    assert PUBLIC_HEPATIC_ADJUSTMENT in html
    assert PUBLIC_PREGNANCY_WARNING in html
    assert PUBLIC_LACTATION_WARNING in html
    assert EXCLUDED_CN not in html
    assert EXCLUDED_NAME not in html
    assert PENDING_CN not in html
    assert PENDING_NAME not in html
    _assert_forbidden_internal_fields_are_absent(html)

    captured = {}

    def fake_render_gft_pdf_bytes(rendered_html):
        captured["html"] = rendered_html
        return b"%PDF fake"

    monkeypatch.setattr(gft_routes, "render_gft_pdf_bytes", fake_render_gft_pdf_bytes)

    pdf_response = client.get("/gft/export/pdf")

    assert pdf_response.status_code == 200
    assert pdf_response.content == b"%PDF fake"
    assert pdf_response.headers["content-type"] == "application/pdf"
    content_disposition = pdf_response.headers["content-disposition"]
    assert "attachment" in content_disposition
    assert "gft-hospitalaria.pdf" in content_disposition

    pdf_html = captured["html"]
    assert PUBLIC_NAME in pdf_html
    assert PUBLIC_CN in pdf_html
    assert PUBLIC_ACTIVE_INGREDIENT in pdf_html
    assert PUBLIC_ATC_CODE in pdf_html
    assert PUBLIC_INDICATIONS in pdf_html
    assert PUBLIC_RESTRICTIONS in pdf_html
    assert PUBLIC_RENAL_ADJUSTMENT in pdf_html
    assert PUBLIC_HEPATIC_ADJUSTMENT in pdf_html
    assert PUBLIC_PREGNANCY_WARNING in pdf_html
    assert PUBLIC_LACTATION_WARNING in pdf_html
    assert EXCLUDED_CN not in pdf_html
    assert EXCLUDED_NAME not in pdf_html
    assert PENDING_CN not in pdf_html
    assert PENDING_NAME not in pdf_html
    _assert_forbidden_internal_fields_are_absent(pdf_html)
