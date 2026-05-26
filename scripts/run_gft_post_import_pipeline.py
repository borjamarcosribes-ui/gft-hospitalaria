#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from scripts import gft_linkage_coverage_audit as audit
from scripts import run_gft_linkage_backfill as linkage
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
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(argv)
    return json.loads(buf.getvalue() or "{}")


def _build_delta(before, after, sections):
    d = {
        "bifimed_con_cache": after.get("bifimed", {}).get("con_cache", 0) - before.get("bifimed", {}).get("con_cache", 0),
        "bifimed_ok": after.get("bifimed", {}).get("sync_status_counts", {}).get("ok", 0) - before.get("bifimed", {}).get("sync_status_counts", {}).get("ok", 0),
        "cima_con_cache": after.get("cima", {}).get("con_cache", 0) - before.get("cima", {}).get("con_cache", 0),
        "cima_ok": after.get("cima", {}).get("ok", 0) - before.get("cima", {}).get("ok", 0),
        "summaries_con_resumen": after.get("summaries", {}).get("con_resumen", 0) - before.get("summaries", {}).get("con_resumen", 0),
        "summaries_con_resumen_general": after.get("summaries", {}).get("con_resumen_general", 0) - before.get("summaries", {}).get("con_resumen_general", 0),
        "clinical_ready": after.get("completion", {}).get("clinical_ready", 0) - before.get("completion", {}).get("clinical_ready", 0),
        "fully_linked_public_detail_ready": after.get("completion", {}).get("fully_linked_public_detail_ready", 0) - before.get("completion", {}).get("fully_linked_public_detail_ready", 0),
    }
    for s in sections:
        key = f"sections_{s.replace('.', '_')}"
        d[key] = after.get("sections", {}).get("coverage_by_section", {}).get(s, 0) - before.get("sections", {}).get("coverage_by_section", {}).get(s, 0)
    return d


def _phase_limit(value, fallback):
    return value if value is not None else fallback


def _require_safety(a):
    if not a.dry_run and not a.confirm_write:
        raise SystemExit("Safe abort: requiere --dry-run o --confirm-write.")
    if a.confirm_write and (a.batch_size is None or a.max_batches is None):
        raise SystemExit("Con --confirm-write requiere --batch-size y --max-batches.")
    if a.confirm_write and any(x is None for x in [a.bifimed_limit, a.cima_med_limit, a.sections_limit, a.summaries_limit]):
        raise SystemExit("Con --confirm-write exige límites por fase (--bifimed-limit/--cima-med-limit/--sections-limit/--summaries-limit).")
    if a.scope in {"imported", "all_known"} and a.batch_size > 200 and not a.i_know_what_i_am_doing:
        raise SystemExit("batch-size > 200 para imported/all_known exige --i-know-what-i-am-doing")


def main(argv=None):
    a = parse_args(argv)
    if a.examples:
        print("PYTHONPATH=. python scripts/run_gft_post_import_pipeline.py --dry-run --scope imported --priority-mode --batch-size 100 --max-batches 1 --bifimed-limit 100 --cima-med-limit 100 --sections-limit 50 --summaries-limit 100 --sections 4.1 4.2 4.3 4.4 4.6 --only-missing --seed-from-imported-urls --repair-not-found-from-imported-url --workers 1 --json")
        return 0

    ensure_postgresql_database(a.allow_default_db)
    _require_safety(a)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    started = time.time()
    started_iso = datetime.now(timezone.utc).isoformat()

    audit_args = ["--scope", a.scope, "--sections", *a.sections, "--json"]
    if a.allow_default_db:
        audit_args.append("--allow-default-db")
    before = _run_json(audit.main, audit_args)

    phase_default = a.batch_size * a.max_batches
    linkage_args = ["--dry-run" if a.dry_run else "--confirm-write", "--scope", a.scope, "--batch-size", str(a.batch_size), "--max-batches", str(a.max_batches), "--sections", *a.sections, "--json"]
    flags = {
        a.only_missing: "--only-missing",
        a.seed_from_imported_urls: "--seed-from-imported-urls",
        a.repair_not_found_from_imported_url: "--repair-not-found-from-imported-url",
        a.refresh_bifimed_ok: "--refresh-bifimed-ok",
        a.retry_bifimed_not_found: "--retry-bifimed-not-found",
        a.skip_bifimed: "--skip-bifimed",
        a.skip_cima_med: "--skip-cima-medicamento",
        a.skip_cima_sections: "--skip-sections",
        a.skip_summaries: "--skip-summaries",
    }
    for cond, flag in flags.items():
        if cond:
            linkage_args.append(flag)
    if a.allow_default_db:
        linkage_args.append("--allow-default-db")

    phases = _run_json(linkage.main, linkage_args)
    after = _run_json(audit.main, audit_args)
    delta = _build_delta(before, after, a.sections)

    ended = time.time()
    elapsed = ended - started
    limits = {
        "bifimed_limit": _phase_limit(a.bifimed_limit, phase_default),
        "cima_med_limit": _phase_limit(a.cima_med_limit, phase_default),
        "sections_limit": _phase_limit(a.sections_limit, phase_default),
        "summaries_limit": _phase_limit(a.summaries_limit, phase_default),
    }

    perf = {
        "started_at": started_iso,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed,
        "phase_elapsed_seconds": {},
        "operations_per_second": (sum(abs(v) for v in delta.values()) / elapsed) if elapsed else 0,
        "external_calls_estimate": phases.get("bifimed", {}).get("processed", 0) + phases.get("cima_medicamento", {}).get("processed", 0),
        "error_count": phases.get("bifimed", {}).get("by_status", {}).get("error", 0) + phases.get("cima_medicamento", {}).get("by_status", {}).get("error", 0),
        "timeout_count": 0,
        "retry_count": 0,
    }

    out = {
        "run_id": run_id,
        "scope": a.scope,
        "dry_run": a.dry_run,
        "priority_mode": a.priority_mode,
        "workers": a.workers,
        "limits": limits,
        "before": before,
        "phases": phases,
        "after": after,
        "delta": delta,
        "performance": perf,
        "next_recommended_command": "PYTHONPATH=. python scripts/run_gft_post_import_pipeline.py --confirm-write --scope imported --priority-mode --batch-size 100 --max-batches 3 --bifimed-limit 300 --cima-med-limit 300 --sections-limit 150 --summaries-limit 250 --sections 4.1 4.2 4.3 4.4 4.6 --only-missing --seed-from-imported-urls --repair-not-found-from-imported-url --workers 3 --sleep-seconds 0.2 --json",
    }
    if sum(abs(v) for v in delta.values()) == 0:
        out["no_progress_reason"] = "dry_run" if a.dry_run else "no_candidates"

    log_dir = Path("runtime_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"gft_post_import_run_{run_id}.json"
    with log_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    out["runtime_log_path"] = str(log_path)

    print(json.dumps(out, ensure_ascii=False, indent=2 if a.json_output else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
