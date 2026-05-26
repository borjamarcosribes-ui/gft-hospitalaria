#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import io
import json

from scripts._db_guard import ensure_postgresql_database
from scripts import gft_linkage_coverage_audit as audit
from scripts import run_gft_linkage_backfill as linkage

DEFAULT_SECTIONS = ["4.1", "4.2", "4.3", "4.4", "4.6"]


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--scope", default="imported", choices=["published", "included", "pending", "imported", "all_known"])
    p.add_argument("--priority-mode", action="store_true")
    p.add_argument("--batch-size", type=int)
    p.add_argument("--max-batches", type=int)
    p.add_argument("--sections", nargs="*", default=DEFAULT_SECTIONS)
    p.add_argument("--only-missing", action="store_true")
    p.add_argument("--seed-from-imported-urls", action="store_true")
    p.add_argument("--repair-not-found-from-imported-url", action="store_true")
    p.add_argument("--refresh-bifimed-ok", action="store_true")
    p.add_argument("--retry-bifimed-not-found", action="store_true")
    p.add_argument("--force-summary", action="store_true")
    p.add_argument("--skip-bifimed", action="store_true")
    p.add_argument("--skip-cima-med", action="store_true")
    p.add_argument("--skip-cima-sections", action="store_true")
    p.add_argument("--skip-summaries", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm-write", action="store_true")
    p.add_argument("--sleep-seconds", type=float, default=0)
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
    delta = {
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
        delta[f"sections_{s.replace('.', '_')}"] = after.get("sections", {}).get("coverage_by_section", {}).get(s, 0) - before.get("sections", {}).get("coverage_by_section", {}).get(s, 0)
    return delta


def main(argv=None):
    a = parse_args(argv)
    ensure_postgresql_database(a.allow_default_db)

    if not a.dry_run and not a.confirm_write:
        raise SystemExit("Safe abort: requiere --dry-run o --confirm-write.")
    if a.confirm_write and (not a.batch_size or not a.max_batches):
        raise SystemExit("Con --confirm-write requiere --batch-size y --max-batches.")
    if a.scope in {"imported", "all_known"} and (a.batch_size or 0) > 200 and not a.i_know_what_i_am_doing:
        raise SystemExit("batch-size > 200 para imported/all_known exige --i-know-what-i-am-doing")

    mode = "--dry-run" if a.dry_run else "--confirm-write"
    batch_size = a.batch_size or 100
    max_batches = a.max_batches or 1

    audit_args = ["--scope", a.scope, "--sections", *a.sections, "--json"]
    if a.allow_default_db:
        audit_args.append("--allow-default-db")
    before = _run_json(audit.main, audit_args)

    linkage_args = [mode, "--scope", a.scope, "--batch-size", str(batch_size), "--max-batches", str(max_batches), "--sections", *a.sections, "--json"]
    if a.only_missing:
        linkage_args.append("--only-missing")
    if a.seed_from_imported_urls:
        linkage_args.append("--seed-from-imported-urls")
    if a.repair_not_found_from_imported_url:
        linkage_args.append("--repair-not-found-from-imported-url")
    if a.refresh_bifimed_ok:
        linkage_args.append("--refresh-bifimed-ok")
    if a.retry_bifimed_not_found:
        linkage_args.append("--retry-bifimed-not-found")
    if a.skip_bifimed:
        linkage_args.append("--skip-bifimed")
    if a.skip_cima_med:
        linkage_args.append("--skip-cima-medicamento")
    if a.skip_cima_sections:
        linkage_args.append("--skip-sections")
    if a.skip_summaries:
        linkage_args.append("--skip-summaries")
    if a.force_summary:
        linkage_args.append("--force-summary")
    if a.allow_default_db:
        linkage_args.append("--allow-default-db")

    phases = _run_json(linkage.main, linkage_args)
    after = _run_json(audit.main, audit_args)
    delta = _build_delta(before, after, a.sections)

    out = {
        "scope": a.scope,
        "priority_mode": a.priority_mode,
        "dry_run": a.dry_run,
        "before": before,
        "phases": {
            "bifimed": phases.get("bifimed", {}),
            "cima_seed": {"enabled": a.seed_from_imported_urls, "repair_not_found": a.repair_not_found_from_imported_url},
            "cima_medicamento": phases.get("cima_medicamento", {}),
            "cima_sections": phases.get("clinical", {}).get("batches", [{}])[0].get("sections", {}),
            "summaries": phases.get("clinical", {}).get("batches", [{}])[0].get("summaries", {}),
        },
        "after": after,
        "delta": delta,
        "next_recommended_command": "PYTHONPATH=. python scripts/run_gft_cache_backfill.py --confirm-write --scope imported --priority-mode --batch-size 100 --max-batches 5 --only-missing --seed-from-imported-urls --repair-not-found-from-imported-url --json",
    }

    if sum(abs(v) for v in delta.values()) == 0:
        out["no_progress_reason"] = "dry_run" if a.dry_run else "no_candidates"

    print(json.dumps(out, ensure_ascii=False, indent=2 if a.json_output else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
