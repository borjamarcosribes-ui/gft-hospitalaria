import json
from sqlalchemy import text

from app.models.bifimed_cache import BifimedCache
from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.services import bifimed_sync_service, cima_sync_service
from app.services.gft_backfill_service import calculate_audit_delta, run_backfill, select_backfill_candidates
from scripts.backfill_gft_enrichment import parse_args


def _create_view(db_session, *, include_cima_urls=False):
    db_session.execute(text("DROP VIEW IF EXISTS v_gft_publicada"))
    indicacion = "'Indicación CIMA de prueba suficientemente larga.'" if include_cima_urls else "NULL"
    db_session.execute(
        text(
            f"""
            CREATE VIEW v_gft_publicada AS
            SELECT
              cn,
              nemonico,
              nombre_comercial_importado AS nombre,
              presentacion_importada AS presentacion,
              forma_farmaceutica_importada AS forma_farmaceutica,
              forma_farmaceutica_importada AS forma_farmaceutica_simplificada,
              NULL AS vias_administracion_json,
              NULL AS atc_json,
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
              {indicacion} AS indicaciones_ficha_tecnica,
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


def _add_gft(db_session, cn, *, published=True, url_ft=None):
    db_session.add(
        GFTEstadoPresentacion(
            cn=cn,
            estado_gft="incluido",
            estado_editorial="publicado" if published else "borrador",
            nemonico=f"N-{cn}",
            nombre_comercial_importado=f"Medicamento {cn}",
            principio_activo_importado="Activo",
            presentacion_importada="Presentación",
            forma_farmaceutica_importada="Comprimido",
            via_administracion_importada="Oral",
            url_ficha_tecnica_importada=url_ft,
        )
    )


def test_candidate_selection_only_published_and_missing_sources(db_session):
    _add_gft(db_session, "100001", published=True)
    _add_gft(db_session, "100002", published=False)
    db_session.add(BifimedCache(cn="100001", sync_status="ok", detalle_financiacion_json={"indicaciones": []}))
    db_session.commit()
    _create_view(db_session)

    candidates = select_backfill_candidates(db_session, source="all")
    keys = {(candidate.cn, candidate.source, candidate.reason) for candidate in candidates}

    assert all(candidate.cn == "100001" for candidate in candidates)
    assert ("100001", "cima", "sin_cima") in keys
    assert ("100001", "bifimed", "bifimed_sin_indicaciones") in keys
    assert ("100001", "clinical", "sin_resumen_clinico") in keys
    assert not any(candidate.cn == "100002" for candidate in candidates)


def test_candidate_selection_detects_missing_bifimed_cache_and_respects_only_missing(db_session):
    _add_gft(db_session, "200001", published=True)
    db_session.commit()
    _create_view(db_session, include_cima_urls=True)

    missing = select_backfill_candidates(db_session, source="bifimed")
    full_scan = select_backfill_candidates(db_session, source="bifimed", only_missing=False)

    assert [(candidate.cn, candidate.reason) for candidate in missing] == [("200001", "sin_bifimed_cache")]
    assert [(candidate.cn, candidate.reason) for candidate in full_scan] == [("200001", "force_or_full_scan")]


def test_candidate_selection_detects_cima_without_indications(db_session):
    _add_gft(db_session, "200002", published=True, url_ft="https://example.test/ft/200002")
    db_session.commit()
    _create_view(db_session)

    candidates = select_backfill_candidates(db_session, source="cima")

    assert [(candidate.cn, candidate.reason) for candidate in candidates] == [("200002", "sin_indicaciones_cima")]


def test_dry_run_does_not_call_sync_and_writes_checkpoint_and_log(db_session, tmp_path, monkeypatch):
    _add_gft(db_session, "300001", published=True)
    db_session.commit()
    _create_view(db_session)
    called = {"cima": 0}

    def fake_sync(db, cn, force=False):
        called["cima"] += 1
        raise AssertionError("dry-run must not sync")

    monkeypatch.setattr(cima_sync_service, "sync_cn", fake_sync)
    checkpoint = tmp_path / "checkpoint.json"
    log_path = tmp_path / "run.jsonl"

    result = run_backfill(
        db_session,
        source="cima",
        mode="dry-run",
        checkpoint_path=checkpoint,
        log_path=log_path,
        sleep_seconds=0,
    )

    assert called["cima"] == 0
    assert result["total_candidates"] == 1
    assert json.loads(checkpoint.read_text())["items"]["cima:300001"]["status"] == "pending"
    record = json.loads(log_path.read_text().splitlines()[0])
    assert record["cn"] == "300001"
    assert record["source"] == "cima"
    assert record["action"] == "dry_run"


def test_checkpoint_resume_skips_successes_and_records_failures(db_session, tmp_path, monkeypatch):
    _add_gft(db_session, "400001", published=True)
    _add_gft(db_session, "400002", published=True)
    db_session.commit()
    _create_view(db_session)
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "started_at": "2026-01-01T00:00:00+00:00",
                "source": "cima",
                "mode": "run",
                "items": {"cima:400001": {"cn": "400001", "source": "cima", "status": "success"}},
            }
        )
    )

    def fake_sync(db, cn, force=False):
        raise RuntimeError("boom")

    monkeypatch.setattr(cima_sync_service, "sync_cn", fake_sync)
    result = run_backfill(
        db_session,
        source="cima",
        mode="run",
        resume=True,
        checkpoint_path=checkpoint,
        log_path=tmp_path / "run.jsonl",
        sleep_seconds=0,
    )

    items = result["checkpoint"]["items"]
    assert items["cima:400001"]["status"] == "success"
    assert items["cima:400002"]["status"] == "error"
    assert result["checkpoint"]["failed"] == 1


def test_run_does_not_overwrite_existing_bifimed_useful_data_with_empty_force(db_session, tmp_path, monkeypatch):
    _add_gft(db_session, "500001", published=True)
    db_session.add(
        BifimedCache(
            cn="500001",
            sync_status="ok",
            situacion_financiacion="Financiado previo",
            indicaciones_autorizadas_json=[{"indicacion_autorizada": "Indicación previa suficiente."}],
        )
    )
    db_session.commit()
    _create_view(db_session)

    def fake_sync(db, cn, force=False):
        row = db.get(BifimedCache, cn)
        row.situacion_financiacion = None
        row.indicaciones_autorizadas_json = []
        row.sync_status = "ok"
        db.commit()
        return row

    monkeypatch.setattr(bifimed_sync_service, "sync_bifimed_cn", fake_sync)
    result = run_backfill(
        db_session,
        source="bifimed",
        mode="run",
        only_missing=False,
        force=True,
        checkpoint_path=tmp_path / "checkpoint.json",
        log_path=tmp_path / "run.jsonl",
        sleep_seconds=0,
    )

    row = db_session.get(BifimedCache, "500001")
    assert row.situacion_financiacion == "Financiado previo"
    assert row.indicaciones_autorizadas_json == [{"indicacion_autorizada": "Indicación previa suficiente."}]
    assert result["checkpoint"]["items"]["bifimed:500001"]["status"] == "unchanged"


def test_audit_delta_calculates_before_after_counters():
    before = {"summary": {"con_cima": 1, "con_bifimed_cache": 2}}
    after = {"summary": {"con_cima": 3, "con_bifimed_cache": 2, "con_indicaciones_bifimed": 1}}

    delta = calculate_audit_delta(before, after)

    assert delta["con_cima"] == {"before": 1, "after": 3, "delta": 2}
    assert delta["con_indicaciones_bifimed"] == {"before": 0, "after": 1, "delta": 1}


def test_cli_defaults_and_source_all_parse():
    args = parse_args(["--source", "all"])

    assert args.source == "all"
    assert args.mode == "dry-run"
    assert args.only_missing is True
    assert args.force is False
