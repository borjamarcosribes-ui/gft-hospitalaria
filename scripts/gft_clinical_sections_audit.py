#!/usr/bin/env python3
"""Auditoría no destructiva de cobertura de secciones clínicas CIMA en medicamentos publicados."""

from __future__ import annotations

import argparse
import json
from sqlalchemy import text
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache

from app.core.database import SessionLocal

TARGET_SECTIONS = ("4.1", "4.2", "4.3", "4.4", "4.6")


def parse_args():
    parser = argparse.ArgumentParser(description="Auditoría de secciones clínicas CIMA para GFT publicada")
    parser.add_argument("--examples", type=int, default=20)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as db:
        rows = db.execute(text("SELECT cn, url_ficha_tecnica FROM v_gft_publicada")).mappings().all()
        total = len(rows)
        cns = [row["cn"] for row in rows]

        with_url = {row["cn"] for row in rows if row.get("url_ficha_tecnica") and str(row.get("url_ficha_tecnica")).strip()}
        without_url = [row["cn"] for row in rows if row["cn"] not in with_url]

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
        "total_publicados": total,
        "con_url_ficha_tecnica": len(with_url),
        "sin_url_ficha_tecnica": len(without_url),
        "con_seccion_4_1": len(coverage["4.1"]),
        "con_seccion_4_2": len(coverage["4.2"]),
        "con_seccion_4_3": len(coverage["4.3"]),
        "con_seccion_4_4": len(coverage["4.4"]),
        "con_seccion_4_6": len(coverage["4.6"]),
        "ejemplos_sin_url_ficha_tecnica": without_url[: args.examples],
        "ejemplos_sin_4_1": sorted(set(cns) - coverage["4.1"])[: args.examples],
        "ejemplos_sin_4_2": sorted(set(cns) - coverage["4.2"])[: args.examples],
        "ejemplos_sin_4_3": sorted(set(cns) - coverage["4.3"])[: args.examples],
        "ejemplos_sin_4_4": sorted(set(cns) - coverage["4.4"])[: args.examples],
        "ejemplos_sin_4_6": sorted(set(cns) - coverage["4.6"])[: args.examples],
    }

    if args.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("GFT Clinical Sections Audit\n")
        for key in (
            "total_publicados",
            "con_url_ficha_tecnica",
            "sin_url_ficha_tecnica",
            "con_seccion_4_1",
            "con_seccion_4_2",
            "con_seccion_4_3",
            "con_seccion_4_4",
            "con_seccion_4_6",
        ):
            print(f"- {key}: {payload[key]}")
        print("\nEjemplos CN sin secciones:")
        print("- sin_4_1:", ", ".join(payload["ejemplos_sin_4_1"]))
        print("- sin_4_2:", ", ".join(payload["ejemplos_sin_4_2"]))
        print("- sin_4_3:", ", ".join(payload["ejemplos_sin_4_3"]))
        print("- sin_4_4:", ", ".join(payload["ejemplos_sin_4_4"]))
        print("- sin_4_6:", ", ".join(payload["ejemplos_sin_4_6"]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
