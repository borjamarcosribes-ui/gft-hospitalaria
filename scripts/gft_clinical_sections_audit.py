#!/usr/bin/env python3
"""Auditoría no destructiva de cobertura de secciones clínicas CIMA en medicamentos publicados."""

from __future__ import annotations

import argparse
import json
import os
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text

from app.core.database import SessionLocal
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache

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
    parser = argparse.ArgumentParser(description="Auditoría de secciones clínicas CIMA para GFT publicada")
    parser.add_argument("--examples", type=int, default=20)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_url = os.getenv("DATABASE_URL")

    with SessionLocal() as db:
        database_name = db.execute(text("SELECT current_database()")).scalar_one_or_none()
        rows = db.execute(text("SELECT cn, url_ficha_tecnica FROM v_gft_publicada")).mappings().all()
        cns = [row["cn"] for row in rows]

        coverage: dict[str, set[str]] = {section: set() for section in TARGET_SECTIONS}
        if cns:
            cache_rows = (
                db.query(CimaFichaTecnicaCache.cn, CimaFichaTecnicaCache.seccion)
                .filter(
                    CimaFichaTecnicaCache.sync_status == "ok",
                    CimaFichaTecnicaCache.cn.in_(cns),
                    CimaFichaTecnicaCache.seccion.in_(TARGET_SECTIONS),
                    CimaFichaTecnicaCache.contenido_texto.is_not(None),
                    text("trim(contenido_texto) <> ''"),
                )
                .all()
            )
            for row in cache_rows:
                coverage[row.seccion].add(row.cn)

    payload = {
        "database_url": _mask_database_url(database_url),
        "database_url_missing": not bool(database_url),
        "database_name": database_name,
        "warning": "WARNING: DATABASE_URL no definido" if not database_url else None,
        "total_publicados": len(rows),
        "con_seccion_4_1": len(coverage["4.1"]),
        "con_seccion_4_2": len(coverage["4.2"]),
        "con_seccion_4_3": len(coverage["4.3"]),
        "con_seccion_4_4": len(coverage["4.4"]),
        "con_seccion_4_6": len(coverage["4.6"]),
        "ejemplos_sin_4_1": sorted(set(cns) - coverage["4.1"])[: args.examples],
        "ejemplos_sin_4_2": sorted(set(cns) - coverage["4.2"])[: args.examples],
        "ejemplos_sin_4_3": sorted(set(cns) - coverage["4.3"])[: args.examples],
        "ejemplos_sin_4_4": sorted(set(cns) - coverage["4.4"])[: args.examples],
        "ejemplos_sin_4_6": sorted(set(cns) - coverage["4.6"])[: args.examples],
    }

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
