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


def test_admin_gft_state_patch_requires_admin_key(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="borrador",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        json={"estado_gft": "incluido"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing admin API key"


def test_admin_gft_state_patch_updates_estado_gft(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="pendiente_revision",
        estado_editorial="borrador",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_gft": "incluido"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["estado_gft"] == "incluido"
    assert body["estado_editorial"] == "borrador"


def test_admin_gft_state_patch_updates_estado_editorial(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="borrador",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_editorial": "validado"},
    )

    assert response.status_code == 200
    assert response.json()["estado_editorial"] == "validado"


def test_admin_gft_state_patch_can_publish_included(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="validado",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_editorial": "publicado", "revisado_por": "Farmacia"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["estado_editorial"] == "publicado"
    assert body["revisado_por"] == "Farmacia"
    assert body["fecha_revision"] is not None


def test_admin_gft_state_patch_can_include_and_publish_same_call(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="pendiente_revision",
        estado_editorial="borrador",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_gft": "incluido", "estado_editorial": "publicado"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["estado_gft"] == "incluido"
    assert body["estado_editorial"] == "publicado"


def test_admin_gft_state_patch_rejects_publishing_non_included(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="pendiente_revision",
        estado_editorial="borrador",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_editorial": "publicado"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Solo se puede publicar un medicamento incluido"


def test_admin_gft_state_patch_rejects_excluding_while_remaining_published(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="publicado",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_gft": "excluido"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Solo se puede publicar un medicamento incluido"
    row = _get_gft_estado(db_session, "111111")
    assert row is not None
    assert row.estado_gft == "incluido"
    assert row.estado_editorial == "publicado"


def test_admin_gft_state_patch_can_unpublish_and_exclude_same_call(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="publicado",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_gft": "excluido", "estado_editorial": "retirado"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["estado_gft"] == "excluido"
    assert body["estado_editorial"] == "retirado"


def test_admin_gft_state_patch_missing_cn_returns_404(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.patch(
        "/admin/gft/medicamentos/999999/estado",
        headers=ADMIN_HEADERS,
        json={"estado_gft": "incluido"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Medicamento GFT no encontrado"


def test_admin_gft_state_patch_rejects_invalid_estado_gft(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_gft": "foo"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "estado_gft inválido"


def test_admin_gft_state_patch_rejects_invalid_estado_editorial(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_editorial": "foo"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "estado_editorial inválido"


def test_admin_gft_state_bulk_requires_admin_key(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111", estado_gft="incluido", estado_editorial="borrador")
    response = client.patch("/admin/gft/medicamentos/estado/bulk", json={"cns": ["111111"], "estado_editorial": "validado"})
    assert response.status_code == 401


def test_admin_gft_state_bulk_updates_multiple_and_not_found(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111", estado_gft="incluido", estado_editorial="borrador")
    _insert_gft_estado(db_session, cn="222222", estado_gft="excluido", estado_editorial="borrador")
    response = client.patch(
        "/admin/gft/medicamentos/estado/bulk",
        headers=ADMIN_HEADERS,
        json={"cns": ["111111", "222222", "999999"], "estado_editorial": "publicado"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requested"] == 3
    assert body["updated"] == 2
    assert body["not_found"] == ["999999"]
    assert _get_gft_estado(db_session, "111111").estado_gft == "incluido"
    assert _get_gft_estado(db_session, "222222").estado_gft == "excluido"


def test_admin_gft_state_bulk_rejects_invalid_editorial_state(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    response = client.patch(
        "/admin/gft/medicamentos/estado/bulk",
        headers=ADMIN_HEADERS,
        json={"cns": ["111111"], "estado_editorial": "foo"},
    )
    assert response.status_code == 400


def test_admin_gft_state_patch_rejects_no_state_changes(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"comentario_revision": "texto"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No hay estados para actualizar"


def test_admin_gft_state_patch_rejects_forbidden_fields(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")

    for payload in (
        {"restricciones_hospitalarias": "texto"},
        {"ajuste_insuficiencia_renal": "texto"},
        {"cn": "222222"},
        {"nemonico": "NEM"},
        {"estado_inventado": "foo"},
    ):
        response = client.patch(
            "/admin/gft/medicamentos/111111/estado",
            headers=ADMIN_HEADERS,
            json=payload,
        )

        assert response.status_code == 422


def test_admin_gft_state_patch_updates_comment_and_reviewer(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="borrador",
    )

    response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={
            "estado_editorial": "validado",
            "comentario_revision": " Revisado ",
            "revisado_por": " Farmacia ",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["comentario_revision"] == "Revisado"
    assert body["revisado_por"] == "Farmacia"
    assert body["fecha_revision"] is not None


def test_admin_gft_state_patch_public_gft_visibility_changes(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="validado",
        nemonico="NEM-111111",
    )
    _create_public_gft_view(db_session)

    before_response = client.get("/gft/medicamentos/111111")
    publish_response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_editorial": "publicado"},
    )
    published_response = client.get("/gft/medicamentos/111111")
    retire_response = client.patch(
        "/admin/gft/medicamentos/111111/estado",
        headers=ADMIN_HEADERS,
        json={"estado_editorial": "retirado"},
    )
    after_response = client.get("/gft/medicamentos/111111")

    assert before_response.status_code == 404
    assert publish_response.status_code == 200
    assert published_response.status_code == 200
    assert published_response.json()["cn"] == "111111"
    assert retire_response.status_code == 200
    assert after_response.status_code == 404
