from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import CIMA_BASE_URL
from app.services.cima_segmented_parser import (
    parse_section_content_json,
    parse_section_text,
    parse_sections_payload,
)


@dataclass
class CimaSegmentedFetchResult:
    status: str
    data: dict | None = None
    error: str | None = None
    raw_payload: dict | None = None


class CimaSegmentedClient:
    def __init__(self, base_url: str = CIMA_BASE_URL, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_sections(self, nregistro: str, tipo_documento: int = 1) -> CimaSegmentedFetchResult:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    f"{self.base_url}/docSegmentado/secciones/{tipo_documento}",
                    params={"nregistro": nregistro},
                    headers={"Accept": "application/json"},
                )
            if resp.status_code == 404:
                return CimaSegmentedFetchResult(status="not_found")
            resp.raise_for_status()
            payload = resp.json()
        except httpx.TimeoutException:
            return CimaSegmentedFetchResult(status="error", error="timeout")
        except Exception as exc:
            return CimaSegmentedFetchResult(status="error", error=str(exc)[:200])

        if isinstance(payload, dict) and "error" in payload:
            return CimaSegmentedFetchResult(status="not_segmented", raw_payload=payload)

        sections = parse_sections_payload(payload)
        if sections is None or sections == []:
            return CimaSegmentedFetchResult(status="not_segmented", raw_payload=payload)

        return CimaSegmentedFetchResult(
            status="ok",
            data={
                "nregistro": nregistro,
                "tipo_documento": tipo_documento,
                "secciones": sections,
            },
            raw_payload=payload,
        )

    def get_section_content(
        self,
        nregistro: str,
        tipo_documento: int = 1,
        seccion: str = "4.1",
    ) -> CimaSegmentedFetchResult:
        endpoint = f"{self.base_url}/docSegmentado/contenido/{tipo_documento}"
        params = {"nregistro": nregistro, "seccion": seccion}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(endpoint, params=params, headers={"Accept": "application/json"})
            if resp.status_code == 404:
                return CimaSegmentedFetchResult(status="not_found")
            resp.raise_for_status()
            payload = resp.json()
        except httpx.TimeoutException:
            return CimaSegmentedFetchResult(status="error", error="timeout")
        except Exception as exc:
            return CimaSegmentedFetchResult(status="error", error=str(exc)[:200])

        if isinstance(payload, dict) and "error" in payload:
            return CimaSegmentedFetchResult(status="section_unavailable", raw_payload={"json": payload})

        parsed_json = parse_section_content_json(payload, requested_section=seccion)
        if parsed_json is None:
            return CimaSegmentedFetchResult(status="section_unavailable", raw_payload={"json": payload})

        contenido_texto = None
        raw_payload: dict[str, Any] = {"json": payload}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                text_resp = client.get(endpoint, params=params, headers={"Accept": "text/plain"})
            text_resp.raise_for_status()
            raw_payload["text"] = text_resp.text
            contenido_texto = parse_section_text(text_resp.text)
        except Exception as exc:
            raw_payload["text_error"] = str(exc)[:200]

        return CimaSegmentedFetchResult(
            status="ok",
            data={
                "nregistro": nregistro,
                "tipo_documento": tipo_documento,
                "seccion": seccion,
                "titulo": parsed_json["titulo"],
                "contenido_html": parsed_json["contenido_html"],
                "contenido_texto": contenido_texto,
            },
            raw_payload=raw_payload,
        )
