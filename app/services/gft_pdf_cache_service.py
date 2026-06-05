from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Callable

from app.services.atc_catalog_service import atc_catalog_fingerprint
from app.services.gft_pdf_export_service import GFTPDFExportData
from app.services.gft_pdf_html_render_service import render_gft_pdf_html
from app.services.gft_pdf_binary_service import render_gft_pdf_bytes

PDF_CACHE_LOGICAL_VERSION = "gft-pdf-narrative-cache-v1"
PDF_CACHE_FILENAME = "gft-hospitalaria.pdf"
_CACHE_DIR_ENV = "GFT_PDF_CACHE_DIR"
_RELEVANT_SERVICE_FILES = (
    "gft_pdf_cache_service.py",
    "gft_pdf_export_service.py",
    "gft_pdf_html_render_service.py",
    "gft_pdf_binary_service.py",
    "atc_catalog_service.py",
)


def get_gft_pdf_cache_dir() -> Path:
    configured_dir = os.getenv(_CACHE_DIR_ENV)
    if configured_dir:
        return Path(configured_dir)
    return Path.cwd() / ".gft_pdf_cache"


def _normalize_mode(mode: str) -> str:
    return "table" if mode == "compact" else mode


def _service_source_fingerprint() -> dict[str, str]:
    services_dir = Path(__file__).resolve().parent
    fingerprints: dict[str, str] = {}
    for filename in _RELEVANT_SERVICE_FILES:
        path = services_dir / filename
        fingerprints[filename] = sha256(path.read_bytes()).hexdigest()
    return fingerprints


def _export_payload(export_data: GFTPDFExportData) -> dict:
    if not is_dataclass(export_data):
        return {"repr": repr(export_data)}
    payload = asdict(export_data)
    payload.pop("generated_at", None)
    return payload


def build_gft_pdf_cache_fingerprint(export_data: GFTPDFExportData, mode: str = "narrative") -> str:
    fingerprint_payload = {
        "cache_version": PDF_CACHE_LOGICAL_VERSION,
        "mode": _normalize_mode(mode),
        "template_services": _service_source_fingerprint(),
        "atc_catalog": atc_catalog_fingerprint(),
        "export_data": _export_payload(export_data),
    }
    canonical_payload = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(canonical_payload.encode("utf-8")).hexdigest()


def _cache_path(fingerprint: str, cache_dir: Path | None = None) -> Path:
    root = cache_dir or get_gft_pdf_cache_dir()
    return root / f"{fingerprint}.pdf"


def get_cached_gft_pdf_bytes(
    export_data: GFTPDFExportData,
    mode: str = "narrative",
    *,
    cache_dir: Path | None = None,
) -> bytes | None:
    path = _cache_path(build_gft_pdf_cache_fingerprint(export_data, mode), cache_dir)
    if not path.is_file():
        return None
    return path.read_bytes()


def get_or_render_cached_gft_pdf_bytes(
    export_data: GFTPDFExportData,
    mode: str = "narrative",
    *,
    html_renderer: Callable[[GFTPDFExportData, str], str] = render_gft_pdf_html,
    pdf_renderer: Callable[[str], bytes] = render_gft_pdf_bytes,
    cache_dir: Path | None = None,
) -> bytes:
    fingerprint = build_gft_pdf_cache_fingerprint(export_data, mode)
    path = _cache_path(fingerprint, cache_dir)
    if path.is_file():
        return path.read_bytes()

    html = html_renderer(export_data, mode)
    pdf_bytes = pdf_renderer(html)

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{fingerprint}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
    return pdf_bytes
