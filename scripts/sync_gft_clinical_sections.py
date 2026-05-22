#!/usr/bin/env python3
"""Sincroniza secciones clínicas CIMA en caché segmentada sin tocar publicación/editorial."""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.services.cima_segmented_sync_service import sync_cima_segmented_section

TARGET_SECTIONS = ("4.1", "4.2", "4.3", "4.4", "4.6")


def _mask_database_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlsplit(url)
    if not parsed.password:
        return url
    auth = f"{parsed.username}:***@{parsed.hostname or ''}"
    if parsed.port:
        auth = f"{auth}:{parsed.port}"
    return urlunsplit((parsed.scheme, auth, parsed.path, parsed.query, parsed.fragment))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync de secciones clínicas desde CIMA para medicamentos publicados")
    parser.add_argument("--sections", nargs="*", default=list(TARGET_SECTIONS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--confirm-write", action="store_true")
    parser.add_argument("--allow-default-db", action="store_true")
    parser.add_argument("--only-missing", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sections = tuple(section for section in args.sections if section in TARGET_SECTIONS)
    if not sections:
        raise SystemExit("No hay secciones válidas. Permitidas: 4.1, 4.2, 4.3, 4.4, 4.6")

    database_url = os.getenv("DATABASE_URL")
    if not database_url and not args.allow_default_db:
        raise SystemExit("WARNING: DATABASE_URL no definido. Bloqueado salvo --allow-default-db")
    if not args.dry_run and not args.confirm_write:
        raise SystemExit("Safe abort: requiere --confirm-write para escritura real.")

    with SessionLocal() as db:
        database_name = db.execute(text("SELECT current_database()")).scalar_one_or_none()
        rows = db.execute(text("SELECT cn FROM v_gft_publicada ORDER BY cn")).mappings().all()
        if args.limit:
            rows = rows[: max(0, args.limit)]
        cns = [row["cn"] for row in rows]

        total_con_cima_cache_ok = (
            db.query(CimaMedicamentoCache)
            .filter(CimaMedicamentoCache.cn.in_(cns), CimaMedicamentoCache.sync_status == "ok")
            .count()
            if cns
            else 0
        )
        total_con_nregistro = (
            db.query(CimaMedicamentoCache)
            .filter(
                CimaMedicamentoCache.cn.in_(cns),
                CimaMedicamentoCache.sync_status == "ok",
                text("trim(coalesce(nregistro, '')) <> ''"),
            )
            .count()
            if cns
            else 0
        )

        by_status = {
            section: {"ok": 0, "not_found": 0, "not_segmented": 0, "section_unavailable": 0, "error": 0}
            for section in sections
        }

        summary = {
            "database_url": _mask_database_url(database_url),
            "database_name": database_name,
            "total_publicados": len(rows),
            "total_con_cima_cache_ok": total_con_cima_cache_ok,
            "total_con_nregistro": total_con_nregistro,
            "requested_sections": list(sections),
            "skipped_missing_cima_cache": 0,
            "skipped_missing_nregistro": 0,
            "examples_problematic_cn": [],
            "by_status": by_status,
        }

        for cn in cns:
            cima_cache = db.get(CimaMedicamentoCache, cn)
            if cima_cache is None or cima_cache.sync_status != "ok":
                summary["skipped_missing_cima_cache"] += 1
                summary["examples_problematic_cn"].append(cn)
                continue

            nregistro = (cima_cache.nregistro or "").strip()
            if not nregistro:
                summary["skipped_missing_nregistro"] += 1
                summary["examples_problematic_cn"].append(cn)
                continue

            for section in sections:
                if args.only_missing:
                    existing_ok = (
                        db.query(CimaFichaTecnicaCache)
                        .filter(
                            CimaFichaTecnicaCache.cn == cn,
                            CimaFichaTecnicaCache.seccion == section,
                            CimaFichaTecnicaCache.sync_status == "ok",
                        )
                        .first()
                    )
                    if existing_ok:
                        continue

                if args.dry_run:
                    continue

                cache_row = sync_cima_segmented_section(
                    db=db,
                    nregistro=nregistro,
                    seccion=section,
                    tipo_documento=1,
                    cn=cn,
                    force=args.force,
                )
                status_key = cache_row.sync_status if cache_row.sync_status in by_status[section] else "error"
                by_status[section][status_key] += 1

        if not args.dry_run:
            db.commit()

    if args.json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
