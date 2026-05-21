#!/usr/bin/env python3
"""Auditoría no destructiva de calidad visible de la GFT pública."""

import argparse
import csv
import datetime
import json
import pathlib
import sys
import urllib.error
import urllib.request

DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_LIMIT_PAGE = 100
MAX_LIMIT_PAGE = 100
EXAMPLE_LIMIT = 30

COUNTER_FIELDS = {
    "sin_nombre": ["nombre"],
    "sin_presentacion": ["presentacion"],
    "sin_forma_farmaceutica": ["forma_farmaceutica", "forma_farmaceutica_simplificada"],
    "sin_via_administracion": ["vias_administracion", "via_administracion"],
    "sin_atc": ["atc", "codigo_atc"],
    "sin_principio_activo": ["principios_activos", "principio_activo"],
    "sin_nemonico": ["nemonico"],
    "sin_indicaciones_ficha_tecnica": ["indicaciones_ficha_tecnica"],
    "sin_situacion_financiacion": ["situacion_financiacion"],
    "sin_url_ficha_tecnica": ["url_ficha_tecnica"],
    "sin_url_prospecto": ["url_prospecto"],
    "sin_restricciones_hospitalarias": ["restricciones_hospitalarias"],
    "sin_ajuste_renal": ["ajuste_insuficiencia_renal", "ajuste_renal"],
    "sin_ajuste_hepatico": ["ajuste_insuficiencia_hepatica", "ajuste_hepatico"],
    "sin_embarazo": ["precauciones_embarazo", "embarazo"],
    "sin_lactancia": ["precauciones_lactancia", "lactancia"],
}

EXAMPLE_FIELDS = {
    "sin_nombre": "ejemplos_sin_nombre",
    "sin_atc": "ejemplos_sin_atc",
    "sin_principio_activo": "ejemplos_sin_principio_activo",
    "sin_indicaciones_ficha_tecnica": "ejemplos_sin_indicaciones",
    "sin_url_ficha_tecnica": "ejemplos_sin_url_ficha_tecnica",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Auditoría de calidad visible de la GFT pública")
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument("--limit-page", type=int, default=DEFAULT_LIMIT_PAGE)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--output-json")
    parser.add_argument("--output-csv")
    parser.add_argument("--fail-threshold-missing-name", type=int, default=0)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args()


def _is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _missing_field(item, fields):
    for field in fields:
        if field in item and not _is_empty(item.get(field)):
            return False
    return True


def fetch_page(backend_url, limit, offset):
    url = f"{backend_url.rstrip('/')}/gft/medicamentos?limit={limit}&offset={offset}"
    request = urllib.request.Request(url=url, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
    return json.loads(body)


def ensure_parent(path_str):
    path = pathlib.Path(path_str)
    parent = path.parent
    if str(parent) == "reports" or str(parent).startswith("reports/"):
        parent.mkdir(parents=True, exist_ok=True)
    return path


def main():
    args = parse_args()
    limit = min(MAX_LIMIT_PAGE, max(1, args.limit_page))

    counters = {"total_publico": 0, "revisados": 0}
    for key in COUNTER_FIELDS:
        counters[key] = 0

    examples = {key: [] for key in EXAMPLE_FIELDS.values()}
    incidencias = []

    try:
        offset = 0
        pages = 0
        while True:
            if args.max_pages is not None and pages >= args.max_pages:
                break
            payload = fetch_page(args.backend_url, limit, offset)
            if not isinstance(payload, dict):
                raise ValueError("Payload JSON no es objeto")

            items = payload.get("items")
            total = payload.get("total")
            if not isinstance(items, list):
                raise ValueError("Campo items no es lista")
            if not isinstance(total, int):
                raise ValueError("Campo total no es entero")

            counters["total_publico"] = total
            if not items:
                break

            for item in items:
                if not isinstance(item, dict):
                    continue
                counters["revisados"] += 1
                cn = str(item.get("cn") or "SIN_CN")
                nombre = item.get("nombre")
                problemas = []

                for counter_key, field_names in COUNTER_FIELDS.items():
                    if _missing_field(item, field_names):
                        counters[counter_key] += 1
                        problemas.append(counter_key)
                        example_key = EXAMPLE_FIELDS.get(counter_key)
                        if example_key and len(examples[example_key]) < EXAMPLE_LIMIT:
                            examples[example_key].append(cn)

                if problemas:
                    incidencias.append({
                        "cn": cn,
                        "nombre": "" if nombre is None else str(nombre),
                        "problemas": "; ".join(problemas),
                    })

            pages += 1
            offset += limit
            if offset >= total:
                break

    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, ValueError) as exc:
        fail_payload = {
            "status": "FAIL",
            "error": str(exc),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        if args.json_output:
            print(json.dumps(fail_payload, ensure_ascii=False, indent=2))
        else:
            print("GFT Public Quality Audit\n")
            print(f"Resultado final:\nFAIL\n\nError técnico: {exc}")
        return 1

    revisados = counters["revisados"]
    percentages = {}
    for key, value in counters.items():
        if key.startswith("sin_"):
            pct_key = "pct_" + key
            percentages[pct_key] = round((value / revisados) * 100, 2) if revisados else 0.0

    result = "WARNING" if counters["sin_nombre"] > args.fail_threshold_missing_name else "OK"

    output_payload = {
        "status": result,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "backend_url": args.backend_url,
        "limit_page": limit,
        "max_pages": args.max_pages,
        "threshold_missing_name": args.fail_threshold_missing_name,
        "counters": counters,
        "percentages": percentages,
        "examples": examples,
    }

    if args.output_json:
        output_path = ensure_parent(args.output_json)
        output_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.output_csv:
        output_csv = ensure_parent(args.output_csv)
        with output_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["cn", "nombre", "problemas"])
            writer.writeheader()
            writer.writerows(incidencias)

    if args.json_output:
        print(json.dumps(output_payload, ensure_ascii=False, indent=2))
    else:
        print("GFT Public Quality Audit\n")
        print(f"Total público: {counters['total_publico']}")
        print(f"Medicamentos revisados: {revisados}\n")
        print("Calidad visible:")
        print(f"- Sin nombre: {counters['sin_nombre']} ({percentages['pct_sin_nombre']}%)")
        print(f"- Sin ATC: {counters['sin_atc']} ({percentages['pct_sin_atc']}%)")
        print(
            f"- Sin principio activo: {counters['sin_principio_activo']} "
            f"({percentages['pct_sin_principio_activo']}%)"
        )
        print(
            "- Sin indicaciones 4.1: "
            f"{counters['sin_indicaciones_ficha_tecnica']} ({percentages['pct_sin_indicaciones_ficha_tecnica']}%)"
        )
        print(
            "- Sin situación financiación: "
            f"{counters['sin_situacion_financiacion']} ({percentages['pct_sin_situacion_financiacion']}%)"
        )
        print("\nEjemplos:")
        print("- Sin nombre: " + ", ".join(examples["ejemplos_sin_nombre"]) )
        print("- Sin ATC: " + ", ".join(examples["ejemplos_sin_atc"]))
        print("- Sin principio activo: " + ", ".join(examples["ejemplos_sin_principio_activo"]))
        print("\nResultado final:")
        print(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
