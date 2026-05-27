#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts import generate_gft_clinical_summaries as summaries
from scripts import gft_linkage_coverage_audit as audit
from scripts import run_gft_bifimed_backfill as bifimed
from scripts import run_gft_cima_medicamento_backfill as cima_med
from scripts import sync_gft_clinical_sections as sections_sync
from scripts._db_guard import ensure_postgresql_database

DEFAULT_SECTIONS = ["4.1", "4.2", "4.3", "4.4", "4.6"]


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm-write", action="store_true")
    p.add_argument("--scope", default="imported", choices=["published", "included", "pending", "imported", "all_known"])
    p.add_argument("--priority-mode", action="store_true")
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--max-batches", type=int, default=1)
    p.add_argument("--sections", nargs="*", default=DEFAULT_SECTIONS)
    p.add_argument("--only-missing", action="store_true")
    p.add_argument("--seed-from-imported-urls", action="store_true")
    p.add_argument("--repair-not-found-from-imported-url", action="store_true")
    p.add_argument("--refresh-bifimed-ok", action="store_true")
    p.add_argument("--retry-bifimed-not-found", action="store_true")
    p.add_argument("--skip-bifimed", action="store_true")
    p.add_argument("--skip-cima-med", action="store_true")
    p.add_argument("--skip-cima-sections", action="store_true")
    p.add_argument("--skip-summaries", action="store_true")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--sleep-seconds", type=float, default=0)
    p.add_argument("--max-runtime-minutes", type=float)
    p.add_argument("--bifimed-limit", type=int)
    p.add_argument("--cima-med-limit", type=int)
    p.add_argument("--sections-limit", type=int)
    p.add_argument("--summaries-limit", type=int)
    p.add_argument("--json", action="store_true", dest="json_output")
    p.add_argument("--examples", action="store_true")
    p.add_argument("--allow-default-db", action="store_true")
    p.add_argument("--i-know-what-i-am-doing", action="store_true")
    return p.parse_args(argv)


def _run_json(fn, argv):
    b = io.StringIO()
    with contextlib.redirect_stdout(b):
        fn(argv)
    return json.loads(b.getvalue() or "{}")


def _build_delta(before, after, req_sections):
    out = {
        "bifimed_con_cache": after.get("bifimed", {}).get("con_cache", 0) - before.get("bifimed", {}).get("con_cache", 0),
        "bifimed_ok": after.get("bifimed", {}).get("sync_status_counts", {}).get("ok", 0) - before.get("bifimed", {}).get("sync_status_counts", {}).get("ok", 0),
        "cima_con_cache": after.get("cima", {}).get("con_cache", 0) - before.get("cima", {}).get("con_cache", 0),
        "cima_ok": after.get("cima", {}).get("ok", 0) - before.get("cima", {}).get("ok", 0),
        "summaries_con_resumen": after.get("summaries", {}).get("con_resumen", 0) - before.get("summaries", {}).get("con_resumen", 0),
        "summaries_con_resumen_general": after.get("summaries", {}).get("con_resumen_general", 0) - before.get("summaries", {}).get("con_resumen_general", 0),
        "clinical_ready": after.get("completion", {}).get("clinical_ready", 0) - before.get("completion", {}).get("clinical_ready", 0),
        "fully_linked_public_detail_ready": after.get("completion", {}).get("fully_linked_public_detail_ready", 0) - before.get("completion", {}).get("fully_linked_public_detail_ready", 0),
    }
    for s in req_sections:
        out[f"sections_{s.replace('.', '_')}"] = after.get("sections", {}).get("coverage_by_section", {}).get(s, 0) - before.get("sections", {}).get("coverage_by_section", {}).get(s, 0)
    return out


def _section_deltas(delta: dict, req_sections: list[str]) -> dict[str, int]:
    return {s: delta.get(f"sections_{s.replace('.', '_')}", 0) for s in req_sections}


def _req_safety(a):
    if a.workers != 1:
        raise SystemExit("workers > 1 todavía no implementado en este wrapper; usa --workers 1")
    if not a.dry_run and not a.confirm_write:
        raise SystemExit("Safe abort: requiere --dry-run o --confirm-write.")
    if a.confirm_write and any(v is None for v in [a.bifimed_limit, a.cima_med_limit, a.sections_limit, a.summaries_limit]):
        raise SystemExit("Con --confirm-write exige límites por fase (--bifimed-limit/--cima-med-limit/--sections-limit/--summaries-limit).")
    if a.scope in {"imported", "all_known"} and a.batch_size > 200 and not a.i_know_what_i_am_doing:
        raise SystemExit("batch-size > 200 para imported/all_known exige --i-know-what-i-am-doing")


def main(argv=None):
    a = parse_args(argv)
    if a.examples:
        print("PYTHONPATH=. python scripts/run_gft_post_import_pipeline.py --dry-run --scope imported --priority-mode --batch-size 100 --max-batches 1 --bifimed-limit 100 --cima-med-limit 100 --sections-limit 50 --summaries-limit 100 --sections 4.1 4.2 4.3 4.4 4.6 --only-missing --seed-from-imported-urls --repair-not-found-from-imported-url --workers 1 --json")
        return 0
    ensure_postgresql_database(a.allow_default_db)
    _req_safety(a)

    default_limit = a.batch_size * a.max_batches
    bifimed_limit = a.bifimed_limit if a.bifimed_limit is not None else default_limit
    cima_limit = a.cima_med_limit if a.cima_med_limit is not None else default_limit
    sections_limit = a.sections_limit if a.sections_limit is not None else default_limit
    summaries_limit = a.summaries_limit if a.summaries_limit is not None else default_limit

    started = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    phase_elapsed = {}

    audit_args = ["--scope", a.scope, "--sections", *a.sections, "--json"]
    if a.allow_default_db:
        audit_args.append("--allow-default-db")

    t = time.time(); before = _run_json(audit.main, audit_args); phase_elapsed["audit_before"] = time.time() - t
    mode = "--dry-run" if a.dry_run else "--confirm-write"
    phases = {}

    if not a.skip_bifimed:
        args = [mode, "--scope", a.scope, "--batch-size", str(bifimed_limit), "--max-batches", "1", "--sleep-seconds", str(a.sleep_seconds), "--json"]
        if a.only_missing: args.append("--only-missing")
        if a.refresh_bifimed_ok: args.append("--refresh-ok")
        if a.retry_bifimed_not_found: args.append("--retry-not-found")
        if a.allow_default_db: args.append("--allow-default-db")
        t = time.time(); phases["bifimed"] = _run_json(bifimed.main, args); phase_elapsed["bifimed"] = time.time() - t

    if not a.skip_cima_med:
        args = [mode, "--scope", a.scope, "--batch-size", str(cima_limit), "--max-batches", "1", "--sleep-seconds", str(a.sleep_seconds), "--json"]
        if a.only_missing: args.append("--only-missing")
        if a.seed_from_imported_urls: args.append("--seed-from-imported-urls")
        if a.repair_not_found_from_imported_url: args.append("--repair-not-found-from-imported-url")
        if a.allow_default_db: args.append("--allow-default-db")
        t = time.time(); phases["cima_medicamento"] = _run_json(cima_med.main, args); phase_elapsed["cima_medicamento"] = time.time() - t

    if not a.skip_cima_sections:
        args = [mode, "--scope", a.scope, "--limit", str(sections_limit), "--sections", *a.sections, "--candidate-mode", "syncable", "--json"]
        if a.only_missing: args.append("--only-missing")
        t = time.time(); phases["cima_sections"] = _run_json(sections_sync.main, args); phase_elapsed["cima_sections"] = time.time() - t

    if not a.skip_summaries:
        args = [mode, "--scope", a.scope, "--limit", str(summaries_limit), "--candidate-mode", "summary_ready", "--json"]
        if a.only_missing: args.append("--only-missing")
        if a.allow_default_db: args.append("--allow-default-db")
        t = time.time(); phases["summaries"] = _run_json(summaries.main, args); phase_elapsed["summaries"] = time.time() - t

    t = time.time(); after = _run_json(audit.main, audit_args); phase_elapsed["audit_after"] = time.time() - t
    delta = _build_delta(before, after, a.sections)

    elapsed = time.time() - started
    err_count = sum(phases.get(k, {}).get("by_status", {}).get("error", 0) for k in ["bifimed", "cima_medicamento", "cima_sections"]) + phases.get("summaries", {}).get("by_source_status", {}).get("error", 0)
    ext_calls = phases.get("bifimed", {}).get("processed", 0) + phases.get("cima_medicamento", {}).get("processed", 0) + phases.get("cima_sections", {}).get("processed_operations", 0)

    clinical_warning = None
    examples_not_counted = []
    section_delta_map = _section_deltas(delta, a.sections)
    section_delta_total = sum(section_delta_map.values())
    cima_sections = phases.get("cima_sections", {}) or {}
    cima_ok = int((cima_sections.get("by_status", {}) or {}).get("ok", 0))
    if not a.skip_cima_sections and cima_ok > 0 and section_delta_total == 0:
        clinical_warning = {
            "code": "sections_ok_but_zero_delta",
            "message": "sync_gft_clinical_sections reportó ok pero el audit no incrementó cobertura de secciones.",
            "cima_sections_ok": cima_ok,
            "section_deltas": section_delta_map,
        }
        examples_not_counted = (after.get("sections", {}) or {}).get("examples_missing_sections", [])[:10]

    out = {
        "run_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "scope": a.scope,
        "priority_mode": a.priority_mode,
        "dry_run": a.dry_run,
        "workers": a.workers,
        "limits": {"bifimed_limit": bifimed_limit, "cima_med_limit": cima_limit, "sections_limit": sections_limit, "summaries_limit": summaries_limit},
        "before": before,
        "phases": phases,
        "after": after,
        "delta": delta,
        "clinical_phase_warning": clinical_warning,
        "examples_sections_written_not_counted": examples_not_counted,
        "post_sections_status_counts": (after.get("sections", {}) or {}).get("post_sections_status_counts", {}),
        "performance": {
            "started_at": started_at,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": elapsed,
            "phase_elapsed_seconds": phase_elapsed,
            "operations_per_second": (sum(abs(v) for v in delta.values()) / elapsed) if elapsed else 0,
            "external_calls_estimate": ext_calls,
            "error_count": err_count,
            "timeout_count": 0,
            "retry_count": 0,
        },
        "next_recommended_command": "PYTHONPATH=. python scripts/run_gft_post_import_pipeline.py --confirm-write --scope imported --priority-mode --batch-size 100 --max-batches 3 --bifimed-limit 300 --cima-med-limit 300 --sections-limit 150 --summaries-limit 250 --sections 4.1 4.2 4.3 4.4 4.6 --only-missing --seed-from-imported-urls --repair-not-found-from-imported-url --workers 1 --sleep-seconds 0.2 --json",
    }
    if sum(abs(v) for v in delta.values()) == 0:
        out["no_progress_reason"] = "dry_run" if a.dry_run else "no_candidates"
    elif clinical_warning:
        out["no_progress_reason"] = "sections_written_not_counted_in_audit"

    Path("runtime_logs").mkdir(exist_ok=True)
    log_path = Path("runtime_logs") / f"gft_post_import_run_{out['run_id']}.json"
    log_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    out["runtime_log_path"] = str(log_path)
    print(json.dumps(out, ensure_ascii=False, indent=2 if a.json_output else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
