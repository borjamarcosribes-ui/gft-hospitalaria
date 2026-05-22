from sqlalchemy import text

from app.models.gft_estado_presentacion import GFTEstadoPresentacion


ADMIN_HEADERS = {"X-Admin-API-Key": "secret"}


def _create_public_gft_view(db_session):
    db_session.execute(text("DROP VIEW IF EXISTS v_gft_publicada"))
    db_session.execute(
        text(
            """
            CREATE VIEW v_gft_publicada AS
            SELECT
              g.cn,
              g.nemonico,
              NULL AS nombre,
              NULL AS presentacion,
              NULL AS forma_farmaceutica,
              NULL AS forma_farmaceutica_simplificada,
              NULL AS vias_administracion_json,
              NULL AS atc_json,
              NULL AS principios_activos_json,
              NULL AS documentos_json,
              NULL AS url_ficha_tecnica,
              NULL AS url_prospecto,
              NULL AS fecha_ficha_tecnica,
              NULL AS fecha_prospecto,
              NULL AS situacion_financiacion,
              NULL AS condiciones_financiacion_restringidas,
              NULL AS condiciones_especiales_financiacion,
              NULL AS estado_nomenclator,
              NULL AS aportacion_usuario,
              NULL AS subgrupo_atc,
              NULL AS indicaciones_ficha_tecnica,
              g.restricciones_hospitalarias,
              g.ajuste_insuficiencia_renal,
              g.ajuste_insuficiencia_hepatica,
              g.precauciones_embarazo,
              g.precauciones_lactancia,
              g.observaciones_internas
            FROM gft_estado_presentacion g
            WHERE g.estado_gft = 'incluido'
              AND g.estado_editorial = 'publicado'
            """
        )
    )
    db_session.commit()


def test_admin_pipeline_requires_admin_key(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")

    response = client.get("/admin/gft/clinical/pipeline-status")

    assert response.status_code == 401


def test_admin_pipeline_returns_blocks(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    _create_public_gft_view(db_session)

    db_session.add(
        GFTEstadoPresentacion(
            cn="111111",
            estado_gft="incluido",
            estado_editorial="publicado",
        )
    )
    db_session.commit()

    response = client.get(
        "/admin/gft/clinical/pipeline-status?limit=20&examples=5&only_missing=true",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    for key in ("audit", "sync_plan", "summary_plan", "recommendation", "safety"):
        assert key in body
    assert body["safety"]["read_only"] is True
    assert body["safety"]["writes_enabled"] is False
