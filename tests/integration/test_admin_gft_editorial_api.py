from sqlalchemy import text

from app.core import config
from app.models.gft_estado_presentacion import GFTEstadoPresentacion


ADMIN_HEADERS = {"X-Admin-API-Key": "secret"}


def _insert_gft_estado(
    db_session,
    cn: str = "111111",
    estado_gft: str = "incluido",
    estado_editorial: str = "publicado",
    **kwargs,
):
    row = GFTEstadoPresentacion(
        cn=cn,
        estado_gft=estado_gft,
        estado_editorial=estado_editorial,
        **kwargs,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _get_gft_estado(db_session, cn: str) -> GFTEstadoPresentacion | None:
    db_session.expire_all()
    return db_session.get(GFTEstadoPresentacion, cn)


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


def test_admin_gft_editorial_patch_requires_admin_key(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")

    response = client.patch(
        "/admin/gft/medicamentos/111111/editorial",
        json={"ajuste_insuficiencia_renal": "Ajustar FG"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing admin API key"


def test_admin_gft_editorial_patch_updates_fields(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="publicado",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/editorial",
        headers=ADMIN_HEADERS,
        json={
            "ajuste_insuficiencia_renal": " Ajustar FG ",
            "precauciones_embarazo": " Evitar salvo criterio ",
            "revisado_por": " Farmacia ",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cn"] == "111111"
    assert body["ajuste_insuficiencia_renal"] == "Ajustar FG"
    assert body["precauciones_embarazo"] == "Evitar salvo criterio"
    assert body["revisado_por"] == "Farmacia"
    assert body["fecha_revision"] is not None

    row = _get_gft_estado(db_session, "111111")
    assert row is not None
    assert row.ajuste_insuficiencia_renal == "Ajustar FG"
    assert row.precauciones_embarazo == "Evitar salvo criterio"
    assert row.revisado_por == "Farmacia"
    assert row.fecha_revision is not None


def test_admin_gft_editorial_patch_clears_field_with_null(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111", ajuste_insuficiencia_renal="Texto previo")

    response = client.patch(
        "/admin/gft/medicamentos/111111/editorial",
        headers=ADMIN_HEADERS,
        json={"ajuste_insuficiencia_renal": None},
    )

    assert response.status_code == 200
    assert response.json()["ajuste_insuficiencia_renal"] is None
    row = _get_gft_estado(db_session, "111111")
    assert row is not None
    assert row.ajuste_insuficiencia_renal is None


def test_admin_gft_editorial_patch_preserves_omitted_fields(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111", ajuste_insuficiencia_hepatica="Texto previo")

    response = client.patch(
        "/admin/gft/medicamentos/111111/editorial",
        headers=ADMIN_HEADERS,
        json={"precauciones_lactancia": "Compatible con vigilancia"},
    )

    assert response.status_code == 200
    row = _get_gft_estado(db_session, "111111")
    assert row is not None
    assert row.precauciones_lactancia == "Compatible con vigilancia"
    assert row.ajuste_insuficiencia_hepatica == "Texto previo"


def test_admin_gft_editorial_patch_missing_cn_returns_404(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.patch(
        "/admin/gft/medicamentos/999999/editorial",
        headers=ADMIN_HEADERS,
        json={"precauciones_lactancia": "Precaución en lactancia"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Medicamento GFT no encontrado"


def test_admin_gft_editorial_patch_rejects_only_revisado_por(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")

    response = client.patch(
        "/admin/gft/medicamentos/111111/editorial",
        headers=ADMIN_HEADERS,
        json={"revisado_por": "Farmacia"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No hay campos para actualizar"


def test_admin_gft_editorial_patch_rejects_forbidden_body_fields(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")

    for payload in ({"estado_gft": "excluido"}, {"estado_editorial": "borrador"}, {"cn": "222222"}):
        response = client.patch(
            "/admin/gft/medicamentos/111111/editorial",
            headers=ADMIN_HEADERS,
            json=payload,
        )

        assert response.status_code == 422


def test_admin_gft_editorial_patch_does_not_change_publication_state(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="publicado",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/editorial",
        headers=ADMIN_HEADERS,
        json={"comentario_revision": "Revisión clínica"},
    )

    assert response.status_code == 200
    row = _get_gft_estado(db_session, "111111")
    assert row is not None
    assert row.estado_gft == "incluido"
    assert row.estado_editorial == "publicado"


def test_admin_gft_editorial_patch_public_gft_reflects_update(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="publicado",
    )
    _create_public_gft_view(db_session)

    update_response = client.patch(
        "/admin/gft/medicamentos/111111/editorial",
        headers=ADMIN_HEADERS,
        json={"ajuste_insuficiencia_renal": "Ajustar FG"},
    )
    public_response = client.get("/gft/medicamentos/111111")

    assert update_response.status_code == 200
    assert public_response.status_code == 200
    assert public_response.json()["ajuste_insuficiencia_renal"] == "Ajustar FG"
