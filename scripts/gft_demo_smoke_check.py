#!/usr/bin/env python3
"""Smoke test no destructivo para validar disponibilidad de la demo GFT."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


DEFAULT_ADMIN_KEY = "demo-local-admin-key"


class EndpointResult:
    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url
        self.ok = False
        self.status_code: int | None = None
        self.error: str | None = None
        self.payload: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "ok": self.ok,
            "status_code": self.status_code,
            "error": self.error,
        }


def fetch_json(url: str, timeout: int, headers: dict[str, str] | None = None) -> EndpointResult:
    result = EndpointResult(name=url, url=url)
    request = urllib.request.Request(url=url, method="GET", headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result.status_code = response.getcode()
            body = response.read().decode("utf-8", errors="replace")
            try:
                result.payload = json.loads(body) if body else None
            except json.JSONDecodeError:
                result.payload = body
            result.ok = True
    except urllib.error.HTTPError as exc:
        result.status_code = exc.code
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        result.error = f"HTTPError: {exc.reason}. Body: {body[:200]}"
    except urllib.error.URLError as exc:
        result.error = f"URLError: {exc.reason}"
    except Exception as exc:  # pylint: disable=broad-except
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def health_status(result: EndpointResult, expected_statuses: set[int], validator=None) -> tuple[bool, str]:
    if not result.ok:
        return False, f"FAIL ({result.error or 'error desconocido'})"
    if result.status_code not in expected_statuses:
        return False, f"FAIL (status={result.status_code})"
    if validator is not None:
        valid, message = validator(result.payload)
        if not valid:
            return False, f"FAIL ({message})"
    return True, "OK"


def validate_health(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload no JSON objeto"
    if payload.get("status") != "ok":
        return False, "status != ok"
    return True, "ok"


def validate_summary(payload: Any) -> tuple[bool, str]:
    required = {"total", "by_estado_gft", "by_estado_editorial", "publicados_en_gft", "quality"}
    if not isinstance(payload, dict):
        return False, "payload no JSON objeto"
    missing = sorted(required - set(payload.keys()))
    if missing:
        return False, f"faltan campos: {', '.join(missing)}"
    return True, "ok"


def validate_items(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload no JSON objeto"
    if "items" not in payload:
        return False, "falta campo items"
    if not isinstance(payload.get("items"), list):
        return False, "items no es lista"
    return True, "ok"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke check de demo GFT")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--frontend-url", default="http://localhost:5173")
    parser.add_argument("--admin-api-key", default=os.getenv("ADMIN_API_KEY"))
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    warnings: list[str] = []
    critical_failure = False

    admin_api_key = args.admin_api_key
    if not admin_api_key:
        admin_api_key = DEFAULT_ADMIN_KEY
        warnings.append("Usando clave demo por defecto para entorno local.")

    backend = args.backend_url.rstrip("/")
    frontend = args.frontend_url.rstrip("/")

    headers = {"X-Admin-API-Key": admin_api_key}

    backend_health = fetch_json(f"{backend}/health", args.timeout)
    admin_health = fetch_json(f"{backend}/admin/health", args.timeout, headers=headers)
    admin_summary = fetch_json(
        f"{backend}/admin/gft/medicamentos/editorial/summary",
        args.timeout,
        headers=headers,
    )
    admin_list = fetch_json(
        f"{backend}/admin/gft/medicamentos/editorial?limit=5&offset=0",
        args.timeout,
        headers=headers,
    )
    public_gft = fetch_json(f"{backend}/gft/medicamentos?limit=20&offset=0", args.timeout)
    frontend_home = fetch_json(frontend, args.timeout)

    checks = [
        ("Backend health", backend_health, {200}, validate_health, True),
        ("Admin health", admin_health, {200}, None, True),
        ("Admin summary", admin_summary, {200}, validate_summary, True),
        ("Admin list", admin_list, {200}, validate_items, True),
        ("Public GFT", public_gft, {200}, validate_items, True),
        ("Frontend", frontend_home, {200, 304}, None, True),
    ]

    lines: list[str] = ["GFT Demo Smoke Check"]
    results: list[dict[str, Any]] = []

    for label, result, statuses, validator, critical in checks:
        is_ok, status_msg = health_status(result, statuses, validator)
        if not is_ok and critical:
            critical_failure = True
        lines.append(f"{label}: {status_msg}")
        if not is_ok:
            lines.append(f"  URL: {result.url}")
            if result.status_code is not None:
                lines.append(f"  Status code: {result.status_code}")
            if result.error:
                lines.append(f"  Error: {result.error}")
        results.append({"label": label, "ok": is_ok, **result.to_dict()})

    summary_payload = admin_summary.payload if isinstance(admin_summary.payload, dict) else {}
    public_payload = public_gft.payload if isinstance(public_gft.payload, dict) else {}

    total_admin = summary_payload.get("total")
    publicados = summary_payload.get("publicados_en_gft")
    total_public = public_payload.get("total")

    quality = summary_payload.get("quality") if isinstance(summary_payload.get("quality"), dict) else {}
    incluidos_no_publicados = quality.get("incluidos_no_publicados")
    sin_cima = quality.get("sin_cima")
    sin_bifimed = quality.get("sin_bifimed")
    sin_ft_41 = quality.get("sin_ficha_tecnica_41")

    if publicados is not None and total_public is not None and publicados != total_public:
        warnings.append(
            "WARNING: publicados_en_gft no coincide con total público "
            f"({publicados} != {total_public})."
        )

    lines.append("")
    lines.append("Resumen:")
    lines.append(f"- Total admin: {total_admin}")
    lines.append(f"- Publicados en GFT: {publicados}")
    lines.append(f"- Total público: {total_public}")
    lines.append(f"- Incluidos no publicados: {incluidos_no_publicados}")
    lines.append(f"- Sin CIMA: {sin_cima}")
    lines.append(f"- Sin BIFIMED: {sin_bifimed}")
    lines.append(f"- Sin FT 4.1: {sin_ft_41}")

    final_status = "FAIL" if critical_failure else ("WARNING" if warnings else "OK")

    if args.json_output:
        print(
            json.dumps(
                {
                    "checks": results,
                    "summary": {
                        "total_admin": total_admin,
                        "publicados_en_gft": publicados,
                        "total_publico": total_public,
                        "incluidos_no_publicados": incluidos_no_publicados,
                        "sin_cima": sin_cima,
                        "sin_bifimed": sin_bifimed,
                        "sin_ficha_tecnica_41": sin_ft_41,
                    },
                    "warnings": warnings,
                    "final_status": final_status,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        if warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in warnings:
                lines.append(f"- {warning}")
        lines.append("")
        lines.append("Resultado final:")
        lines.append(final_status)
        print("\n".join(lines))

    return 1 if critical_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
