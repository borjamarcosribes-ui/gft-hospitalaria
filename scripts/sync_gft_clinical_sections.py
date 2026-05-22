#!/usr/bin/env python3
"""Sincroniza secciones clínicas CIMA en caché segmentada sin tocar publicación/editorial."""

from __future__ import annotations

import argparse
import json
from app.core.database import SessionLocal
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.services.cima_segmented_sync_service import sync_cima_segmented_section
from sqlalchemy import text

TARGET_SECTIONS = ("4.2", "4.3", "4.4", "4.6")


def parse_args():
    parser = argparse.ArgumentParser(description="Sync de secciones clínicas desde CIMA para medicamentos publicados")
    parser.add_argument("--sections", nargs="*", default=list(TARGET_SECTIONS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sections = tuple(section for section in args.sections if section in TARGET_SECTIONS)
    if not sections:
        raise SystemExit("No hay secciones válidas. Permitidas: 4.2, 4.3, 4.4, 4.6")

    with SessionLocal() as db:
        public_rows = db.execute(text("SELECT cn FROM v_gft_publicada ORDER BY cn")).mappings().all()
        if args.limit:
            public_rows = public_rows[: max(0, args.limit)]

        summary = {
            "total_publicados": len(public_rows),
            "sections": list(sections),
            "dry_run": args.dry_run,
            "force": args.force,
            "synced": 0,
            "skipped_missing_cima_cache": 0,
            "skipped_missing_nregistro": 0,
            "by_status": {"ok": 0, "not_found": 0, "not_segmented": 0, "section_unavailable": 0, "error": 0},
        }

        for row in public_rows:
            cn = row["cn"]
            cima_cache = db.get(CimaMedicamentoCache, cn)
            if cima_cache is None or cima_cache.sync_status != "ok":
                summary["skipped_missing_cima_cache"] += 1
                continue
            nregistro = (cima_cache.nregistro or "").strip()
            if not nregistro:
                summary["skipped_missing_nregistro"] += 1
                continue

            for section in sections:
                if args.dry_run:
                    summary["synced"] += 1
                    continue
                cache_row = sync_cima_segmented_section(
                    db=db,
                    nregistro=nregistro,
                    seccion=section,
                    tipo_documento=1,
                    cn=cn,
                    force=args.force,
                )
                summary["synced"] += 1
                key = cache_row.sync_status if cache_row.sync_status in summary["by_status"] else "error"
                summary["by_status"][key] += 1

    if args.json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
