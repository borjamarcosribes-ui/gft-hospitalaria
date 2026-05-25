#!/usr/bin/env python3
import argparse
import json
from collections import Counter

from sqlalchemy import text

from app.db import SessionLocal
from app.services.gft_query_service import _expand_atc_code, _extract_atc_items_from_row


def main() -> int:
    parser = argparse.ArgumentParser(description="ATC coverage audit for published GFT medications")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    parser.add_argument("--examples", type=int, default=20, help="Number of example rows")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT cn, nombre, atc_json, codigo_atc_importado, descripcion_atc_importada
                FROM v_gft_publicada
                """
            )
        ).mappings().all()

        l1_counts: Counter[str] = Counter()
        level_codes: dict[str, set[str]] = {"L1": set(), "L2": set(), "L3": set(), "L4": set(), "L5": set()}
        con_atc_efectivo = 0
        con_atc_json = 0
        con_atc_importado_fallback = 0
        examples_sin_atc = []
        examples_fallback = []

        for row in rows:
            items = _extract_atc_items_from_row(row)
            if items:
                con_atc_efectivo += 1
            else:
                if len(examples_sin_atc) < args.examples:
                    examples_sin_atc.append({"cn": row.get("cn"), "nombre": row.get("nombre")})
                continue

            has_json = bool(row.get("atc_json"))
            if has_json:
                con_atc_json += 1
            else:
                con_atc_importado_fallback += 1
                if len(examples_fallback) < args.examples:
                    examples_fallback.append(
                        {
                            "cn": row.get("cn"),
                            "nombre": row.get("nombre"),
                            "codigo_atc_importado": row.get("codigo_atc_importado"),
                            "descripcion_atc_importada": row.get("descripcion_atc_importada"),
                        }
                    )

            seen_codes = set()
            for item in items:
                code = str(item.get("codigo") or "")
                for expanded_code, level in _expand_atc_code(code):
                    if expanded_code in seen_codes:
                        continue
                    seen_codes.add(expanded_code)
                    level_codes[level].add(expanded_code)
                    if level == "L1":
                        l1_counts[expanded_code] += 1

        payload = {
            "total_publicados": len(rows),
            "con_atc_efectivo": con_atc_efectivo,
            "sin_atc": len(rows) - con_atc_efectivo,
            "con_atc_json": con_atc_json,
            "con_atc_importado_fallback": con_atc_importado_fallback,
            "l1_counts": dict(sorted(l1_counts.items())),
            "levels": {level: len(codes) for level, codes in level_codes.items()},
            "examples_sin_atc": examples_sin_atc,
            "examples_fallback_importado": examples_fallback,
        }

        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"Total publicados: {payload['total_publicados']}")
            print(f"Con ATC efectivo: {payload['con_atc_efectivo']}")
            print(f"Sin ATC: {payload['sin_atc']}")
            print(f"Con atc_json: {payload['con_atc_json']}")
            print(f"Fallback importado: {payload['con_atc_importado_fallback']}")
            print(f"L1: {payload['l1_counts']}")
            print(f"Niveles únicos: {payload['levels']}")

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
