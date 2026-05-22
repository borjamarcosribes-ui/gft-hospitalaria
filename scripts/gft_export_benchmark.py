#!/usr/bin/env python3
"""Benchmark no destructivo para exportaciones públicas GFT (HTML/PDF)."""

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mide estado HTTP, tamaño y tiempos de exportaciones GFT."
    )
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--timeout-html", type=int, default=60)
    parser.add_argument("--timeout-pdf", type=int, default=180)
    parser.add_argument("--output-json")
    parser.add_argument("--download-dir", default="reports/export_benchmark")
    parser.add_argument("--skip-pdf", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_stdout")
    return parser.parse_args()


def _request(url: str, timeout_seconds: int, output_path: Path | None = None) -> dict:
    started = time.perf_counter()
    request = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            elapsed = time.perf_counter() - started
            status = getattr(response, "status", response.getcode())
            content_type = response.headers.get("Content-Type", "")
            if output_path is not None:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(body)
            return {
                "status": status,
                "content_type": content_type,
                "bytes": len(body),
                "time_seconds": round(elapsed, 3),
                "body": body,
                "error": None,
                "timeout": False,
            }
    except TimeoutError as exc:
        elapsed = time.perf_counter() - started
        return {
            "status": "timeout",
            "content_type": "",
            "bytes": 0,
            "time_seconds": round(elapsed, 3),
            "body": b"",
            "error": str(exc),
            "timeout": True,
        }
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - started
        body = exc.read() if hasattr(exc, "read") else b""
        return {
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "bytes": len(body),
            "time_seconds": round(elapsed, 3),
            "body": body,
            "error": str(exc),
            "timeout": False,
        }
    except urllib.error.URLError as exc:
        elapsed = time.perf_counter() - started
        is_timeout = isinstance(exc.reason, TimeoutError)
        return {
            "status": "timeout" if is_timeout else "error",
            "content_type": "",
            "bytes": 0,
            "time_seconds": round(elapsed, 3),
            "body": b"",
            "error": str(exc),
            "timeout": is_timeout,
        }


def _build_report(args: argparse.Namespace) -> dict:
    base_url = args.backend_url.rstrip("/")
    download_dir = Path(args.download_dir)

    html = _request(
        f"{base_url}/gft/export/html",
        timeout_seconds=args.timeout_html,
        output_path=download_dir / "gft-export.html",
    )

    html_text = html["body"].decode("utf-8", errors="ignore")
    html.update(
        {
            "has_title": "Guía Farmacoterapéutica Hospitalaria" in html_text,
            "has_total_publicados": "Total de medicamentos publicados" in html_text,
        }
    )

    pdf = None
    if not args.skip_pdf:
        pdf = _request(
            f"{base_url}/gft/export/pdf",
            timeout_seconds=args.timeout_pdf,
            output_path=download_dir / "gft-hospitalaria.pdf",
        )
        pdf.update({"valid_pdf": pdf["body"].startswith(b"%PDF")})

    html_ok = (
        html["status"] == 200
        and html["has_title"]
        and html["has_total_publicados"]
    )

    if not html_ok:
        result = "FAIL"
        exit_code = 1
    elif args.skip_pdf:
        result = "OK"
        exit_code = 0
    elif pdf and pdf["status"] == 200 and pdf["valid_pdf"]:
        result = "OK"
        exit_code = 0
    elif pdf and pdf["timeout"]:
        result = "WARNING"
        exit_code = 0
    else:
        result = "FAIL"
        exit_code = 1

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend_url": base_url,
        "html": html,
        "pdf": pdf,
        "result": result,
        "exit_code": exit_code,
    }


def _print_text(report: dict, skip_pdf: bool) -> None:
    html = report["html"]
    print("GFT Export Benchmark")
    print()
    print("HTML:")
    print(f"- status: {html['status']}")
    print(f"- content-type: {html['content_type']}")
    print(f"- size: {html['bytes']}")
    print(f"- time: {html['time_seconds']}s")
    print(f"- has_title: {'yes' if html['has_title'] else 'no'}")
    print(f"- has_total_publicados: {'yes' if html['has_total_publicados'] else 'no'}")
    print()

    if not skip_pdf:
        pdf = report["pdf"]
        print("PDF:")
        print(f"- status: {pdf['status']}")
        print(f"- content-type: {pdf['content_type']}")
        print(f"- size: {pdf['bytes']}")
        print(f"- time: {pdf['time_seconds']}s")
        print(f"- valid_pdf: {'yes' if pdf.get('valid_pdf') else 'no'}")
        print()

    print(f"Resultado: {report['result']}")


def main() -> int:
    args = parse_args()
    report = _build_report(args)

    serializable = {
        **report,
        "html": {k: v for k, v in report["html"].items() if k != "body"},
        "pdf": None
        if report["pdf"] is None
        else {k: v for k, v in report["pdf"].items() if k != "body"},
    }

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(serializable, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if args.json_stdout:
        print(json.dumps(serializable, indent=2, ensure_ascii=False))
    else:
        _print_text(serializable, skip_pdf=args.skip_pdf)

    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
