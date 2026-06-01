import json
from sqlalchemy import text

import pytest

from app.models.bifimed_cache import BifimedCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
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


def _add_gft(db_session, cn, *, published=True, url_ft=None, estado_gft="incluido"):
    db_session.add(
        GFTEstadoPresentacion(
            cn=cn,
            estado_gft=estado_gft,
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
    db_session.commit()
    _create_view(db_session)

    candidates = select_backfill_candidates(db_session, source="all")
    keys = {(candidate.cn, candidate.source, candidate.reason) for candidate in candidates}

    assert all(candidate.cn == "100001" for candidate in candidates)
    assert ("100001", "cima", "sin_cima") in keys
    assert ("100001", "bifimed", "sin_bifimed_cache") in keys
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


def test_candidate_selection_skips_cima_without_indications_by_default(db_session):
    _add_gft(db_session, "200002", published=True, url_ft="https://example.test/ft/200002")
    db_session.commit()
    _create_view(db_session)

    candidates = select_backfill_candidates(db_session, source="cima")

    assert candidates == []


def test_candidate_selection_includes_cima_without_indications_when_requested(db_session):
    _add_gft(db_session, "200003", published=True, url_ft="https://example.test/ft/200003")
    db_session.commit()
    _create_view(db_session)

    candidates = select_backfill_candidates(db_session, source="cima", include_incomplete=True)

    assert [(candidate.cn, candidate.reason) for candidate in candidates] == [("200003", "sin_indicaciones_cima")]


def test_candidate_selection_skips_bifimed_without_indications_by_default(db_session):
    _add_gft(db_session, "200004", published=True)
    db_session.add(BifimedCache(cn="200004", sync_status="ok", detalle_financiacion_json={"indicaciones": []}))
    db_session.commit()
    _create_view(db_session)

    candidates = select_backfill_candidates(db_session, source="bifimed")

    assert candidates == []


def test_candidate_selection_includes_bifimed_without_indications_when_requested(db_session):
    _add_gft(db_session, "200005", published=True)
    db_session.add(BifimedCache(cn="200005", sync_status="ok", detalle_financiacion_json={"indicaciones": []}))
    db_session.commit()
    _create_view(db_session)

    candidates = select_backfill_candidates(db_session, source="bifimed", include_incomplete=True)

    assert [(candidate.cn, candidate.reason) for candidate in candidates] == [("200005", "bifimed_sin_indicaciones")]


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
    assert args.include_incomplete is False
    assert args.force is False


def test_cli_include_incomplete_parse():
    args = parse_args(["--source", "bifimed", "--include-incomplete"])

    assert args.include_incomplete is True


def test_dry_run_cima_prefers_missing_cache_over_incomplete_batch(db_session, tmp_path):
    for idx in range(10):
        _add_gft(db_session, f"6100{idx:02d}", published=True, url_ft=f"https://example.test/ft/6100{idx:02d}")
    for idx in range(3):
        _add_gft(db_session, f"6200{idx:02d}", published=True)
    db_session.commit()
    _create_view(db_session)

    result = run_backfill(
        db_session,
        source="cima",
        mode="dry-run",
        limit=50,
        checkpoint_path=tmp_path / "checkpoint.json",
        log_path=tmp_path / "run.jsonl",
        sleep_seconds=0,
    )

    items = result["checkpoint"]["items"].values()
    assert len(items) == 3
    assert {item["reason"] for item in items} == {"sin_cima"}
    assert not any(item["reason"] == "sin_indicaciones_cima" for item in items)


def test_cli_scope_defaults_and_valid_values_parse():
    default_args = parse_args(["--source", "all"])
    master_args = parse_args(["--source", "cima", "--scope", "all-imported"])
    excel_args = parse_args(["--source", "bifimed", "--scope", "excel-master"])

    assert default_args.scope == "gft-publicada"
    assert master_args.scope == "all-imported"
    assert excel_args.scope == "excel-master"


def test_cli_invalid_scope_fails():
    with pytest.raises(SystemExit):
        parse_args(["--scope", "inventado"])


def test_candidate_selection_all_imported_includes_unpublished_and_deduplicates_valid_cn(db_session):
    _add_gft(db_session, "012345", published=True)
    _add_gft(db_session, "222222", published=False)
    _add_gft(db_session, "333333", published=False, estado_gft="excluido")
    _add_gft(db_session, "ABC123", published=False)
    db_session.commit()
    _create_view(db_session)

    candidates = select_backfill_candidates(db_session, source="cima", scope="all-imported")

    assert [(candidate.cn, candidate.source, candidate.reason) for candidate in candidates] == [
        ("012345", "cima", "sin_cima"),
        ("222222", "cima", "sin_cima"),
        ("333333", "cima", "sin_cima"),
    ]
    assert candidates[0].cn == "012345"


def test_candidate_selection_all_imported_skips_existing_cima_cache_with_only_missing(db_session):
    _add_gft(db_session, "700001", published=False)
    _add_gft(db_session, "700002", published=False)
    db_session.add(CimaMedicamentoCache(cn="700001", sync_status="ok"))
    db_session.commit()

    candidates = select_backfill_candidates(db_session, source="cima", scope="all-imported")

    assert [(candidate.cn, candidate.reason) for candidate in candidates] == [("700002", "sin_cima")]


def test_candidate_selection_all_imported_skips_existing_bifimed_cache_with_only_missing(db_session):
    _add_gft(db_session, "710001", published=False)
    _add_gft(db_session, "710002", published=False)
    db_session.add(BifimedCache(cn="710001", sync_status="ok", detalle_financiacion_json={"indicaciones": []}))
    db_session.commit()

    candidates = select_backfill_candidates(db_session, source="bifimed", scope="all-imported")

    assert [(candidate.cn, candidate.reason) for candidate in candidates] == [("710002", "sin_bifimed_cache")]


def test_candidate_selection_all_imported_include_incomplete_cima(db_session):
    _add_gft(db_session, "720001", published=False)
    db_session.add(CimaMedicamentoCache(cn="720001", sync_status="ok", url_ficha_tecnica=None))
    db_session.commit()

    default_candidates = select_backfill_candidates(db_session, source="cima", scope="all-imported")
    incomplete_candidates = select_backfill_candidates(
        db_session,
        source="cima",
        scope="all-imported",
        include_incomplete=True,
    )

    assert default_candidates == []
    assert [(candidate.cn, candidate.reason) for candidate in incomplete_candidates] == [
        ("720001", "cima_cache_incompleto")
    ]


def test_candidate_selection_all_imported_include_incomplete_bifimed(db_session):
    _add_gft(db_session, "730001", published=False)
    db_session.add(BifimedCache(cn="730001", sync_status="ok", detalle_financiacion_json={"indicaciones": []}))
    db_session.commit()

    default_candidates = select_backfill_candidates(db_session, source="bifimed", scope="all-imported")
    incomplete_candidates = select_backfill_candidates(
        db_session,
        source="bifimed",
        scope="all-imported",
        include_incomplete=True,
    )

    assert default_candidates == []
    assert [(candidate.cn, candidate.reason) for candidate in incomplete_candidates] == [
        ("730001", "bifimed_sin_indicaciones")
    ]


def test_dry_run_all_imported_writes_scope_and_does_not_sync(db_session, tmp_path, monkeypatch):
    _add_gft(db_session, "740001", published=False)
    db_session.commit()
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
        scope="all-imported",
        mode="dry-run",
        checkpoint_path=checkpoint,
        log_path=log_path,
        sleep_seconds=0,
    )

    checkpoint_payload = json.loads(checkpoint.read_text())
    record = json.loads(log_path.read_text().splitlines()[0])
    assert called["cima"] == 0
    assert result["scope"] == "all-imported"
    assert result["total_universe"] == 1
    assert checkpoint_payload["scope"] == "all-imported"
    assert checkpoint_payload["items"]["cima:740001"]["scope"] == "all-imported"
    assert record["scope"] == "all-imported"
