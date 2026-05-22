#!/usr/bin/env python3
"""Genera resúmenes clínicos automáticos desde secciones CIMA cacheadas."""

from __future__ import annotations

import argparse
import json

from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.gft_clinical_summary_cache import GftClinicalSummaryCache
from app.services.gft_clinical_summary_service import build_clinical_summary

TARGET_SECTIONS = ("4.1", "4.2", "4.3", "4.4", "4.6")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--cn")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-write", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--only-missing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run and not args.confirm_write:
        raise SystemExit("Safe abort: requiere --confirm-write para escritura real.")

    summary = {"processed": 0, "generated": 0, "skipped_unchanged": 0, "total_publicados": 0}

    with SessionLocal() as db:
        public_cns = [
            row["cn"]
            for row in db.execute(text("SELECT cn FROM v_gft_publicada ORDER BY cn")).mappings().all()
        ]
        summary["total_publicados"] = len(public_cns)

        cns = public_cns
        if args.cn:
            cns = [args.cn] if args.cn in public_cns else []
        if args.limit:
            cns = cns[: max(0, args.limit)]

        for cn in cns:
            summary["processed"] += 1
            current = db.get(GftClinicalSummaryCache, cn)
            if args.only_missing and current and current.source_status in ("ok", "partial"):
                continue

            cima_cache = db.get(CimaMedicamentoCache, cn)
            has_cima_ok = bool(cima_cache and cima_cache.sync_status == "ok")
            has_nregistro = bool((cima_cache.nregistro if cima_cache else "") or "")

            rows = (
                db.query(CimaFichaTecnicaCache)
                .filter(
                    CimaFichaTecnicaCache.cn == cn,
                    CimaFichaTecnicaCache.seccion.in_(TARGET_SECTIONS),
                    CimaFichaTecnicaCache.sync_status == "ok",
                )
                .all()
            )
            sections = {row.seccion: (row.contenido_texto or "") for row in rows}
            data = build_clinical_summary(sections, has_nregistro=has_nregistro, has_cima_ok=has_cima_ok)

            if (
                current
                and current.source_hash == data["source_hash"]
                and current.source_status in ("ok", "partial")
                and not args.force
            ):
                summary["skipped_unchanged"] += 1
                continue

            if not args.dry_run:
                row = current or GftClinicalSummaryCache(cn=cn)
                for key, value in data.items():
                    if not key.startswith("_"):
                        setattr(row, key, value)
                db.add(row)

            summary["generated"] += 1

        if not args.dry_run:
            db.commit()

    if args.json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
