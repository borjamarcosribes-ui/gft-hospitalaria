from io import BytesIO
from types import SimpleNamespace

import pandas as pd
from sqlalchemy import text

from app.models.bifimed_cache import BifimedCache
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services.bifimed_client import BifimedFetchResult
from app.services.cima_segmented_client import CimaSegmentedFetchResult


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
        "gft-workflow.xlsx",
        _make_excel(rows),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def test_full_gft_import_workflow_from_excel_to_public_gft(client, db_session, monkeypatch):
    upload_response = client.post(
        "/imports/excel",
        files={
            "file": _excel_file(
                [
                    {
                        "CN": "111111",
                        "Observaciones revisión": "SI",
                        "Estado editorial": "publicado",
                        "Nemónico": "NEM-111111",
                        "Restricciones hospitalarias": "Uso restringido test",
                        "Observaciones internas GFT": "Observación visible test",
                    },
                    {
                        "CN": "222222",
                        "Observaciones revisión": "NO",
                        "Estado editorial": "publicado",
                        "Nemónico": "NEM-222222",
                    },
                    {
                        "CN": "333333",
                        "Observaciones revisión": "guía",
                        "Estado editorial": "publicado",
                        "Nemónico": "NEM-333333",
                    },
                ]
            )
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["status"] == "validated"
    assert upload_payload["total_rows"] == 3
    batch_id = upload_payload["batch_id"]
    assert batch_id

    assert db_session.query(GFTEstadoPresentacion).count() == 0

    summary_response = client.get(f"/imports/{batch_id}/summary")

    assert summary_response.status_code == 200
    summary_payload = summary_response.json()
    assert summary_payload["staging_total_rows"] == 3
    assert summary_payload["included_rows"] == 1
    assert summary_payload["excluded_rows"] == 1
    assert summary_payload["pending_rows"] == 1
    assert summary_payload["applicable_rows"] == 2
    assert summary_payload["skipped_pending"] == 1

    called_cns = []

    def fake_get_by_cn(self, cn):
        called_cns.append(cn)
        if cn != "111111":
            raise AssertionError(f"Unexpected CIMA call for CN {cn}")
        return SimpleNamespace(
            status="ok",
            error=None,
            raw_payload={"test": "payload"},
            data={
                "nregistro": "NR111111",
                "nombre": "Paracetamol Test",
                "presentacion": "Paracetamol Test 1 g comprimidos",
                "forma_farmaceutica": "Comprimido",
                "forma_farmaceutica_simplificada": "comprimido",
                "vias_administracion_json": [{"nombre": "Vía oral"}],
                "atc_json": [{"codigo": "N02BE01", "nombre": "Paracetamol", "nivel": "L5"}],
                "principios_activos_json": [{"nombre": "Paracetamol"}],
                "documentos_json": [
                    {"tipo": 1, "url": "https://example.test/ft/111111"},
                    {"tipo": 2, "url": "https://example.test/pr/111111"},
                ],
                "url_ficha_tecnica": "https://example.test/ft/111111",
                "url_prospecto": "https://example.test/pr/111111",
                "fecha_ficha_tecnica": None,
                "fecha_prospecto": None,
            },
        )

    monkeypatch.setattr("app.services.cima_sync_service.CimaClient.get_by_cn", fake_get_by_cn)

    sync_response = client.post(f"/cima/sync/import-batch/{batch_id}?force=true")

    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["eligible_cn"] == 1
    assert sync_payload["ok"] == 1
    assert sync_payload["skipped_excluded"] == 1
    assert sync_payload["skipped_pending"] == 1
    assert sync_payload["error"] == 0
    assert sync_payload["not_found"] == 0
    assert called_cns == ["111111"]

    db_session.expire_all()
    assert db_session.query(GFTEstadoPresentacion).count() == 0
    cima_cache = db_session.get(CimaMedicamentoCache, "111111")
    assert cima_cache is not None
    assert cima_cache.sync_status == "ok"
    assert cima_cache.nregistro == "NR111111"

    called_segmented_nregistros = []

    def fake_segmented_get_section_content(
        self, nregistro, tipo_documento=1, seccion="4.1"
    ):
        called_segmented_nregistros.append(nregistro)
        if nregistro != "NR111111":
            raise AssertionError(f"Unexpected CIMA segmented call for nregistro {nregistro}")
        return CimaSegmentedFetchResult(
            status="ok",
            data={
                "nregistro": nregistro,
                "tipo_documento": tipo_documento,
                "seccion": seccion,
                "titulo": "Indicaciones terapéuticas",
                "contenido_html": "<div><p>Indicación test FT</p></div>",
                "contenido_texto": "Indicación test FT",
            },
            error=None,
            raw_payload={"json": [{"seccion": seccion}], "text": "Indicación test FT"},
        )

    monkeypatch.setattr(
        "app.services.cima_segmented_client.CimaSegmentedClient.get_section_content",
        fake_segmented_get_section_content,
    )

    segmented_sync_response = client.post(
        f"/cima/segmented/sync/import-batch/{batch_id}?force=true"
    )

    assert segmented_sync_response.status_code == 200
    segmented_sync_payload = segmented_sync_response.json()
    assert segmented_sync_payload["eligible_cn"] == 1
    assert segmented_sync_payload["total_cn"] == 1
    assert segmented_sync_payload["eligible_nregistro"] == 1
    assert segmented_sync_payload["total_nregistro"] == 1
    assert segmented_sync_payload["ok"] == 1
    assert segmented_sync_payload["error"] == 0
    assert segmented_sync_payload["not_found"] == 0
    assert segmented_sync_payload["not_segmented"] == 0
    assert segmented_sync_payload["section_unavailable"] == 0
    assert segmented_sync_payload["skipped_excluded"] == 1
    assert segmented_sync_payload["skipped_pending"] == 1
    assert called_segmented_nregistros == ["NR111111"]

    db_session.expire_all()
    assert db_session.query(GFTEstadoPresentacion).count() == 0
    segmented_cache = (
        db_session.query(CimaFichaTecnicaCache)
        .filter_by(nregistro="NR111111", tipo_documento=1, seccion="4.1")
        .one_or_none()
    )
    assert segmented_cache is not None
    assert segmented_cache.sync_status == "ok"
    assert segmented_cache.contenido_texto == "Indicación test FT"
    assert segmented_cache.cn == "111111"

    called_bifimed_cns = []

    def fake_bifimed_get_by_cn(self, cn):
        called_bifimed_cns.append(cn)
        if cn != "111111":
            raise AssertionError(f"Unexpected BIFIMED call for CN {cn}")
        return BifimedFetchResult(
            status="ok",
            data={
                "situacion_financiacion": "Si",
                "condiciones_financiacion_restringidas": "Visado",
                "condiciones_especiales_financiacion": "Financiación especial test",
                "estado_nomenclator": "ALTA",
                "aportacion_usuario": "NORMAL",
                "subgrupo_atc": "N02BE01 - Paracetamol",
                "detalle_financiacion_json": {
                    "Código nacional": "111111",
                    "Situación de financiación": "Si",
                    "Condiciones financiación restringidas": "Visado",
                    "Condiciones especiales de financiación": "Financiación especial test",
                    "Estado de Nomenclátor": "ALTA",
                    "Aportación usuario": "NORMAL",
                    "Subgrupo ATC/Descripción": "N02BE01 - Paracetamol",
                },
            },
            error=None,
            raw_payload={"test": "bifimed-payload"},
        )

    monkeypatch.setattr(
        "app.services.bifimed_sync_service.BifimedClient.get_by_cn", fake_bifimed_get_by_cn
    )

    bifimed_sync_response = client.post(f"/bifimed/sync/import-batch/{batch_id}?force=true")

    assert bifimed_sync_response.status_code == 200
    bifimed_sync_payload = bifimed_sync_response.json()
    assert bifimed_sync_payload["eligible_cn"] == 1
    assert bifimed_sync_payload["ok"] == 1
    assert bifimed_sync_payload["skipped_excluded"] == 1
    assert bifimed_sync_payload["skipped_pending"] == 1
    assert bifimed_sync_payload["error"] == 0
    assert bifimed_sync_payload["not_found"] == 0
    assert called_bifimed_cns == ["111111"]

    db_session.expire_all()
    assert db_session.query(GFTEstadoPresentacion).count() == 0
    bifimed_cache = db_session.get(BifimedCache, "111111")
    assert bifimed_cache is not None
    assert bifimed_cache.sync_status == "ok"
    assert bifimed_cache.situacion_financiacion == "Si"

    apply_response = client.post(f"/imports/{batch_id}/apply")

    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert apply_payload["applied_rows"] == 2
    assert apply_payload["skipped_pending"] == 1

    db_session.expire_all()
    row_111111 = db_session.get(GFTEstadoPresentacion, "111111")
    assert row_111111 is not None
    assert row_111111.estado_gft == "incluido"
    assert row_111111.estado_editorial == "publicado"
    row_222222 = db_session.get(GFTEstadoPresentacion, "222222")
    assert row_222222 is not None
    assert row_222222.estado_gft == "excluido"
    assert row_222222.estado_editorial == "publicado"
    assert db_session.get(GFTEstadoPresentacion, "333333") is None

    _create_view(db_session)

    list_response = client.get("/gft/medicamentos")

    assert list_response.status_code == 200
    list_payload = list_response.json()
    listed_cns = [item["cn"] for item in list_payload["items"]]
    assert list_payload["total"] == 1
    assert list_payload["items"][0]["cn"] == "111111"
    assert list_payload["items"][0]["nombre"] == "Paracetamol Test"
    assert list_payload["items"][0]["situacion_financiacion"] == "Si"
    assert list_payload["items"][0]["indicaciones_ficha_tecnica"] == "Indicación test FT"
    assert list_payload["items"][0]["ajuste_insuficiencia_renal"] is None
    assert list_payload["items"][0]["ajuste_insuficiencia_hepatica"] is None
    assert list_payload["items"][0]["precauciones_embarazo"] is None
    assert list_payload["items"][0]["precauciones_lactancia"] is None
    assert list_payload["items"][0]["url_ficha_tecnica"] == "https://example.test/ft/111111"
    assert list_payload["items"][0]["url_prospecto"] == "https://example.test/pr/111111"
    assert "222222" not in listed_cns
    assert "333333" not in listed_cns

    detail_response = client.get("/gft/medicamentos/111111")

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["cn"] == "111111"
    assert detail_payload["nombre"] == "Paracetamol Test"
    assert detail_payload["nemonico"] == "NEM-111111"
    assert detail_payload["restricciones_hospitalarias"] == "Uso restringido test"
    assert detail_payload["indicaciones_ficha_tecnica"] == "Indicación test FT"
    assert detail_payload["ajuste_insuficiencia_renal"] is None
    assert detail_payload["ajuste_insuficiencia_hepatica"] is None
    assert detail_payload["precauciones_embarazo"] is None
    assert detail_payload["precauciones_lactancia"] is None
    assert detail_payload["observaciones_internas_publicables"] == "Observación visible test"
    assert detail_payload["financiacion_detalle"] == {
        "situacion_financiacion": "Si",
        "condiciones_financiacion_restringidas": "Visado",
        "condiciones_especiales_financiacion": "Financiación especial test",
        "estado_nomenclator": "ALTA",
        "aportacion_usuario": "NORMAL",
        "subgrupo_atc": "N02BE01 - Paracetamol",
    }
    assert any(item["codigo"] == "N02BE01" for item in detail_payload["atc"])
    assert "Vía oral" in detail_payload["vias_administracion"]
    assert {doc["url"] for doc in detail_payload["documentos"]} == {
        "https://example.test/ft/111111",
        "https://example.test/pr/111111",
    }

    assert client.get("/gft/medicamentos/222222").status_code == 404
    assert client.get("/gft/medicamentos/333333").status_code == 404
