from dataclasses import dataclass
from datetime import date
from typing import Any
import httpx
from app.core.config import CIMA_BASE_URL


@dataclass
class CimaFetchResult:
    status: str
    data: dict | None = None
    error: str | None = None
    raw_payload: dict | None = None


class CimaClient:
    def __init__(self, base_url: str = CIMA_BASE_URL, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_by_cn(self, cn: str) -> CimaFetchResult:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.base_url}/medicamentos", params={"cn": cn})
            if resp.status_code == 404:
                return CimaFetchResult(status="not_found")
            resp.raise_for_status()
            payload = resp.json()
        except httpx.TimeoutException:
            return CimaFetchResult(status="error", error="timeout")
        except Exception as exc:
            return CimaFetchResult(status="error", error=str(exc)[:200])

        med = self._extract_medicamento(payload)
        if not med:
            return CimaFetchResult(status="not_found", raw_payload=payload if isinstance(payload, dict) else None)
        mapped = self._map_medicamento(med)
        return CimaFetchResult(status="ok", data=mapped, raw_payload=payload if isinstance(payload, dict) else None)

    def _extract_medicamento(self, payload: Any) -> dict | None:
        if isinstance(payload, dict):
            if isinstance(payload.get("resultados"), list) and payload["resultados"]:
                return payload["resultados"][0]
            if isinstance(payload.get("medicamentos"), list) and payload["medicamentos"]:
                return payload["medicamentos"][0]
            if any(k in payload for k in ["nombre", "nregistro", "docs", "atc"]):
                return payload
        return None

    def _map_medicamento(self, med: dict) -> dict:
        docs = self._extract_docs(med)
        url_ft, fecha_ft = self._pick_doc(docs, 1)
        url_pr, fecha_pr = self._pick_doc(docs, 2)
        return {
            "nregistro": med.get("nregistro"),
            "nombre": med.get("nombre"),
            "presentacion": med.get("presentacion"),
            "forma_farmaceutica": med.get("formaFarmaceutica") or med.get("forma_farmaceutica"),
            "forma_farmaceutica_simplificada": med.get("formaFarmaceuticaSimplificada") or med.get("forma_farmaceutica_simplificada"),
            "vias_administracion_json": med.get("viasAdministracion") or med.get("vias_administracion"),
            "atc_json": med.get("atc"),
            "principios_activos_json": med.get("principiosActivos") or med.get("principios_activos"),
            "documentos_json": docs,
            "url_ficha_tecnica": url_ft,
            "url_prospecto": url_pr,
            "fecha_ficha_tecnica": fecha_ft,
            "fecha_prospecto": fecha_pr,
        }

    def _extract_docs(self, med: dict) -> list[dict]:
        out = []
        for d in (med.get("docs") or med.get("documentos") or []):
            if not isinstance(d, dict):
                continue
            out.append({
                "tipo": d.get("tipo"),
                "url": d.get("url"),
                "urlHtml": d.get("urlHtml"),
                "secc": d.get("secc"),
                "fecha": d.get("fecha"),
                "titulo": d.get("nombre") or d.get("titulo"),
            })
        return out

    def _pick_doc(self, docs: list[dict], tipo: int):
        for d in docs:
            if d.get("tipo") == tipo:
                fecha = self._parse_date(d.get("fecha"))
                return d.get("url") or d.get("urlHtml"), fecha
        return None, None

    def _parse_date(self, value: str | None):
        if not value:
            return None
        try:
            return date.fromisoformat(value[:10])
        except Exception:
            return None
