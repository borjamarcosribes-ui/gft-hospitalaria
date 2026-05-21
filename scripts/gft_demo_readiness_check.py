#!/usr/bin/env python3
"""Check integral no destructivo de preparación de demo GFT (solo GET)."""

import argparse
import datetime
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_FRONTEND_URL = "http://localhost:5173"
DEFAULT_ADMIN_KEY = "demo-local-admin-key"
SEARCH_TERMS = ["ABARAX", "ABILIFY", "ACETILCISTEINA"]
QUALITY_FIELDS = {
    "sin_nombre": ["nombre"],
    "sin_atc": ["atc", "codigo_atc"],
    "sin_principio_activo": ["principios_activos", "principio_activo"],
    "sin_indicaciones_ficha_tecnica": ["indicaciones_ficha_tecnica"],
    "sin_situacion_financiacion": ["situacion_financiacion"],
}


def read_env_value(key):
    try:
        raw = pathlib.Path("/proc/self/environ").read_bytes().split(b"\x00")
    except OSError:
        return None
    for entry in raw:
        if entry.startswith((key + "=").encode("utf-8")):
            return entry.decode("utf-8", errors="replace").split("=", 1)[1]
    return None


def is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def missing_fields(item, fields):
    for field in fields:
        if field in item and not is_empty(item.get(field)):
            return False
    return True


def fetch(url, timeout, headers=None):
    req = urllib.request.Request(url=url, method="GET", headers=headers or {})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            return {
                "ok": True,
                "status": response.getcode(),
                "body": body,
                "content_type": content_type,
                "elapsed_ms": int((time.time() - started) * 1000),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return {
            "ok": False,
            "status": exc.code,
            "body": body,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "elapsed_ms": int((time.time() - started) * 1000),
            "error": f"HTTPError: {exc.reason}",
        }
    except urllib.error.URLError as exc:
        return {"ok": False, "status": None, "body": b"", "content_type": "", "elapsed_ms": int((time.time() - started) * 1000), "error": f"URLError: {exc.reason}"}


def parse_json_response(resp):
    try:
        return json.loads(resp["body"].decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def parse_args():
    p = argparse.ArgumentParser(description="GFT Demo Readiness Check")
    p.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    p.add_argument("--frontend-url", default=DEFAULT_FRONTEND_URL)
    p.add_argument("--admin-api-key", default=None)
    p.add_argument("--timeout", type=int, default=10)
    p.add_argument("--expected-public-total", type=int)
    p.add_argument("--expected-no-missing-name", action="store_true")
    p.add_argument("--check-pdf", action="store_true")
    p.add_argument("--strict-quality", action="store_true")
    p.add_argument("--output-json")
    p.add_argument("--json", action="store_true", dest="json_output")
    return p.parse_args()


def main():
    args = parse_args()
    warnings = []
    failures = []

    admin_api_key = args.admin_api_key or read_env_value("ADMIN_API_KEY")
    if not admin_api_key:
        admin_api_key = DEFAULT_ADMIN_KEY
        warnings.append("ADMIN_API_KEY no definida; usando demo-local-admin-key")

    backend = args.backend_url.rstrip("/")
    frontend = args.frontend_url.rstrip("/")
    admin_headers = {"X-Admin-API-Key": admin_api_key}

    health = fetch(f"{backend}/health", args.timeout)
    health_json = parse_json_response(health)
    backend_ok = health["status"] == 200 and isinstance(health_json, dict) and health_json.get("status") == "ok"
    if not backend_ok:
        failures.append("Backend health falló")

    admin_health = fetch(f"{backend}/admin/health", args.timeout, admin_headers)
    admin_summary = fetch(f"{backend}/admin/gft/medicamentos/editorial/summary", args.timeout, admin_headers)
    admin_list = fetch(f"{backend}/admin/gft/medicamentos/editorial?limit=5&offset=0", args.timeout, admin_headers)
    admin_summary_json = parse_json_response(admin_summary)
    admin_list_json = parse_json_response(admin_list)
    admin_ok = admin_health["status"] == 200 and admin_summary["status"] == 200 and admin_list["status"] == 200 and isinstance(admin_summary_json, dict) and isinstance(admin_list_json, dict)
    if not admin_ok:
        failures.append("Admin endpoints fallaron")

    public_first = fetch(f"{backend}/gft/medicamentos?limit=20&offset=0", args.timeout)
    public_first_json = parse_json_response(public_first)
    public_items = public_first_json.get("items") if isinstance(public_first_json, dict) else None
    public_total = public_first_json.get("total") if isinstance(public_first_json, dict) else None
    public_ok = public_first["status"] == 200 and isinstance(public_items, list) and len(public_items) > 0 and isinstance(public_total, int) and public_total > 0
    if not public_ok:
        failures.append("Endpoint público de medicamentos falló")

    if isinstance(public_total, int) and args.expected_public_total is not None and public_total != args.expected_public_total:
        warnings.append(f"Total público distinto al esperado ({public_total} != {args.expected_public_total})")

    search_results = []
    for term in SEARCH_TERMS:
        resp = fetch(f"{backend}/gft/medicamentos?q={term}&limit=20&offset=0", args.timeout)
        payload = parse_json_response(resp)
        total = payload.get("total") if isinstance(payload, dict) else None
        status = "OK"
        if resp["status"] != 200:
            failures.append(f"Búsqueda {term} falló")
            status = "FAIL"
        elif isinstance(total, int) and total == 0:
            warnings.append(f"Búsqueda {term} sin resultados")
            status = "WARNING"
        search_results.append({"q": term, "status": status, "total": total, "http_status": resp["status"]})

    atc = fetch(f"{backend}/gft/atc", args.timeout)
    atc_json = parse_json_response(atc)
    atc_nodes = 0
    if isinstance(atc_json, list):
        atc_nodes = len(atc_json)
    elif isinstance(atc_json, dict):
        if isinstance(atc_json.get("items"), list):
            atc_nodes = len(atc_json["items"])
        elif isinstance(atc_json.get("data"), list):
            atc_nodes = len(atc_json["data"])
    atc_ok = atc["status"] == 200 and atc_nodes >= 0
    if atc["status"] != 200:
        failures.append("Índice ATC no disponible")
    if public_ok and atc_nodes == 0:
        warnings.append("Índice ATC vacío con pública no vacía")

    frontend_resp = fetch(frontend, args.timeout)
    frontend_ok = frontend_resp["status"] in (200, 304)
    if not frontend_ok:
        failures.append("Frontend no disponible")

    # calidad pública (iteración paginada GET)
    quality = {k: 0 for k in QUALITY_FIELDS}
    reviewed = 0
    offset = 0
    limit = 100
    quality_error = None
    while public_ok and offset < public_total:
        page = fetch(f"{backend}/gft/medicamentos?limit={limit}&offset={offset}", args.timeout)
        page_json = parse_json_response(page)
        if page["status"] != 200 or not isinstance(page_json, dict) or not isinstance(page_json.get("items"), list):
            quality_error = "No se pudo completar auditoría de calidad pública"
            break
        items = page_json.get("items", [])
        if not items:
            break
        for item in items:
            if not isinstance(item, dict):
                continue
            reviewed += 1
            for key, fields in QUALITY_FIELDS.items():
                if missing_fields(item, fields):
                    quality[key] += 1
        offset += limit

    if quality_error:
        warnings.append(quality_error)
    if args.expected_no_missing_name and quality.get("sin_nombre", 0) > 0:
        warnings.append(f"sin_nombre > 0 ({quality['sin_nombre']})")
    quality_observations = []
    for key, value in quality.items():
        if key != "sin_nombre" and value > 0:
            quality_observations.append(f"{key}={value}")

    if args.strict_quality and any(quality[k] > 0 for k in quality):
        warnings.append("Calidad pública incompleta (modo estricto)")

    pdf_status = "No comprobado"
    pdf_info = {}
    if args.check_pdf:
        pdf = fetch(f"{backend}/gft/export/pdf", args.timeout)
        if pdf["status"] == 404:
            pdf_status = "WARNING"
            warnings.append("PDF endpoint no disponible todavía")
        elif pdf["status"] == 200:
            size = len(pdf["body"])
            ctype = (pdf["content_type"] or "").lower()
            if "application/pdf" in ctype and size > 1000:
                pdf_status = "OK"
            else:
                pdf_status = "WARNING"
                warnings.append("PDF respondió pero content-type/tamaño no esperado")
            pdf_info = {"content_type": pdf["content_type"], "size": size}
        elif pdf["status"] is None:
            pdf_status = "FAIL"
            failures.append("No se pudo conectar al endpoint PDF")
        else:
            pdf_status = "WARNING"
            warnings.append(f"Endpoint PDF devolvió status {pdf['status']}")

    final_status = "FAIL" if failures else ("WARNING" if warnings else "OK")
    exit_code = 1 if failures else 0

    total_admin = admin_summary_json.get("total") if isinstance(admin_summary_json, dict) else None
    public_admin = admin_summary_json.get("publicados_en_gft") if isinstance(admin_summary_json, dict) else None

    report = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "backend_url": backend,
        "frontend_url": frontend,
        "connectivity": {
            "backend": "OK" if backend_ok else "FAIL",
            "frontend": "OK" if frontend_ok else "FAIL",
            "admin": "OK" if admin_ok else "FAIL",
        },
        "data": {
            "total_admin": total_admin,
            "publicados_en_gft": public_admin,
            "total_publico": public_total,
            "revisados_calidad": reviewed,
            **quality,
        },
        "searches": search_results,
        "atc": {"status": "OK" if atc_ok else "FAIL", "nodes": atc_nodes},
        "pdf": {"status": pdf_status, **pdf_info},
        "quality_observations": quality_observations,
        "warnings": warnings,
        "failures": failures,
        "final_status": final_status,
    }

    if args.output_json:
        out_path = pathlib.Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json_output:
        try:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        except TypeError:
            print(json.dumps({"final_status": "FAIL", "error": "JSON inválido"}, ensure_ascii=False))
            return 1
    else:
        print("GFT Demo Readiness Check\n")
        print("Conectividad:")
        print(f"- Backend: {'OK' if backend_ok else 'FAIL'}")
        print(f"- Frontend: {'OK' if frontend_ok else 'FAIL'}")
        print(f"- Admin: {'OK' if admin_ok else 'FAIL'}")
        print("\nDatos:")
        print(f"- Total admin: {total_admin}")
        print(f"- Publicados en GFT: {public_admin}")
        print(f"- Total público: {public_total}")
        print(f"- Sin nombre: {quality['sin_nombre']}")
        print(f"- Sin ATC: {quality['sin_atc']}")
        print(f"- Sin principio activo: {quality['sin_principio_activo']}")
        print(f"- Sin indicaciones ficha técnica: {quality['sin_indicaciones_ficha_tecnica']}")
        print(f"- Sin situación financiación: {quality['sin_situacion_financiacion']}")
        print("\nBúsquedas:")
        for item in search_results:
            print(f"- {item['q']}: {item['status']}")
        print("\nÍndice ATC:")
        print(f"- {'OK' if atc_ok else 'FAIL'}")
        print("\nPDF:")
        print(f"- {pdf_status}")
        print("\nObservaciones de calidad:")
        if quality_observations:
            for obs in quality_observations:
                print(f"- {obs}")
        else:
            print("- Ninguna")
        if warnings:
            print("\nWarnings:")
            for warn in warnings:
                print(f"- {warn}")
        if failures:
            print("\nErrores críticos:")
            for fail in failures:
                print(f"- {fail}")
        print("\nResultado final:")
        print(final_status)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
