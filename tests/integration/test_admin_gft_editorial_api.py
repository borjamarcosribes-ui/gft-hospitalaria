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


def test_admin_gft_editorial_get_requires_admin_key(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")

    response = client.get("/admin/gft/medicamentos/111111/editorial")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing admin API key"


def test_admin_gft_editorial_get_returns_existing_editorial_state(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="borrador",
        nemonico="NEMO",
        ajuste_insuficiencia_renal="Ajustar FG",
        precauciones_embarazo="Evitar",
    )

    response = client.get("/admin/gft/medicamentos/111111/editorial", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["cn"] == "111111"
    assert body["estado_gft"] == "incluido"
    assert body["estado_editorial"] == "borrador"
    assert body["nemonico"] == "NEMO"
    assert body["ajuste_insuficiencia_renal"] == "Ajustar FG"
    assert body["precauciones_embarazo"] == "Evitar"
    assert "last_import_batch_id" in body
    assert "last_imported_at" in body


def test_admin_gft_editorial_get_returns_unpublished_rows(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="pendiente_revision",
        estado_editorial="borrador",
        ajuste_insuficiencia_hepatica="Precaución",
    )
    _create_public_gft_view(db_session)

    response = client.get("/admin/gft/medicamentos/111111/editorial", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["cn"] == "111111"
    assert body["estado_gft"] == "pendiente_revision"
    assert body["estado_editorial"] == "borrador"
    assert body["ajuste_insuficiencia_hepatica"] == "Precaución"


def test_admin_gft_editorial_get_missing_cn_returns_404(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/admin/gft/medicamentos/999999/editorial", headers=ADMIN_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"] == "Medicamento GFT no encontrado"


def test_admin_gft_editorial_get_empty_cn_returns_400(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/admin/gft/medicamentos/%20%20/editorial", headers=ADMIN_HEADERS)

    assert response.status_code == 400
    assert response.json()["detail"] == "CN obligatorio"


def test_admin_gft_editorial_get_does_not_create_rows(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/admin/gft/medicamentos/999999/editorial", headers=ADMIN_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"] == "Medicamento GFT no encontrado"
    assert db_session.query(GFTEstadoPresentacion).count() == 0


def test_admin_gft_editorial_patch_then_get_returns_updated_values(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="borrador",
        ajuste_insuficiencia_renal="Texto previo",
    )

    patch_response = client.patch(
        "/admin/gft/medicamentos/111111/editorial",
        headers=ADMIN_HEADERS,
        json={"ajuste_insuficiencia_renal": "Ajustar FG actualizado"},
    )
    get_response = client.get("/admin/gft/medicamentos/111111/editorial", headers=ADMIN_HEADERS)

    assert patch_response.status_code == 200
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["cn"] == "111111"
    assert body["estado_gft"] == "incluido"
    assert body["estado_editorial"] == "borrador"
    assert body["ajuste_insuficiencia_renal"] == "Ajustar FG actualizado"


def test_admin_gft_editorial_list_requires_admin_key(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/admin/gft/medicamentos/editorial")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing admin API key"


def test_admin_gft_editorial_list_returns_rows(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(
        db_session,
        cn="111111",
        estado_gft="incluido",
        estado_editorial="publicado",
        nemonico="AAA",
    )
    _insert_gft_estado(
        db_session,
        cn="222222",
        estado_gft="pendiente_revision",
        estado_editorial="borrador",
        nemonico="BBB",
    )

    response = client.get("/admin/gft/medicamentos/editorial", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert [item["cn"] for item in body["items"]] == ["111111", "222222"]
    assert body["items"][0]["estado_editorial"] == "publicado"
    assert body["items"][1]["estado_editorial"] == "borrador"
    assert "observaciones_internas" not in body["items"][0]
    assert "comentario_revision" not in body["items"][0]


def test_admin_gft_editorial_list_filters_by_estado_gft(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111", estado_gft="incluido")
    _insert_gft_estado(db_session, cn="222222", estado_gft="pendiente_revision")

    response = client.get(
        "/admin/gft/medicamentos/editorial?estado_gft=pendiente_revision",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["cn"] for item in body["items"]] == ["222222"]
    assert body["items"][0]["estado_gft"] == "pendiente_revision"


def test_admin_gft_editorial_list_filters_by_estado_editorial(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111", estado_editorial="publicado")
    _insert_gft_estado(db_session, cn="222222", estado_editorial="borrador")

    response = client.get(
        "/admin/gft/medicamentos/editorial?estado_editorial=borrador",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["cn"] for item in body["items"]] == ["222222"]
    assert body["items"][0]["estado_editorial"] == "borrador"


def test_admin_gft_editorial_list_filters_by_q_cn_or_nemonico(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111", nemonico="ALFA")
    _insert_gft_estado(db_session, cn="222222", nemonico="BETA")

    alfa_response = client.get("/admin/gft/medicamentos/editorial?q=ALFA", headers=ADMIN_HEADERS)
    cn_response = client.get("/admin/gft/medicamentos/editorial?q=222", headers=ADMIN_HEADERS)

    assert alfa_response.status_code == 200
    assert [item["cn"] for item in alfa_response.json()["items"]] == ["111111"]
    assert cn_response.status_code == 200
    assert [item["cn"] for item in cn_response.json()["items"]] == ["222222"]


def test_admin_gft_editorial_list_filters_by_q_clinical_text(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111", ajuste_insuficiencia_renal="Ajustar FG")
    _insert_gft_estado(db_session, cn="222222", ajuste_insuficiencia_renal="Sin ajuste")

    response = client.get("/admin/gft/medicamentos/editorial?q=fg", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["cn"] for item in body["items"]] == ["111111"]


def test_admin_gft_editorial_list_paginates(client, db_session, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")
    _insert_gft_estado(db_session, cn="222222")
    _insert_gft_estado(db_session, cn="333333")

    response = client.get(
        "/admin/gft/medicamentos/editorial?limit=2&offset=1", headers=ADMIN_HEADERS
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert [item["cn"] for item in body["items"]] == ["222222", "333333"]


def test_admin_gft_editorial_list_rejects_invalid_limit(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    for limit in (0, 201):
        response = client.get(
            f"/admin/gft/medicamentos/editorial?limit={limit}", headers=ADMIN_HEADERS
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "limit debe estar entre 1 y 200"


def test_admin_gft_editorial_list_rejects_invalid_offset(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")

    response = client.get("/admin/gft/medicamentos/editorial?offset=-1", headers=ADMIN_HEADERS)

    assert response.status_code == 400
    assert response.json()["detail"] == "offset debe ser mayor o igual a 0"


def test_admin_gft_editorial_list_route_order_does_not_treat_editorial_as_cn(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "secret")
    _insert_gft_estado(db_session, cn="111111")

    response = client.get("/admin/gft/medicamentos/editorial", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["cn"] == "111111"
