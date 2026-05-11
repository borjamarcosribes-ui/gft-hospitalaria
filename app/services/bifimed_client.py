from dataclasses import dataclass

import httpx

from app.core.config import BIFIMED_BASE_URL
from app.services.bifimed_parser import parse_bifimed_detail_html


@dataclass
class BifimedFetchResult:
    status: str
    data: dict | None = None
    error: str | None = None
    raw_payload: dict | None = None


class BifimedClient:
    def __init__(self, base_url: str = BIFIMED_BASE_URL, timeout: float = 10.0):
        self.base_url = base_url
        self.timeout = timeout

    def get_by_cn(self, cn: str) -> BifimedFetchResult:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(self.base_url, params={"cn": cn, "metodo": "verDetalle"})
            if resp.status_code == 404:
                return BifimedFetchResult(status="not_found")
            resp.raise_for_status()
            html = resp.text
        except httpx.TimeoutException:
            return BifimedFetchResult(status="error", error="timeout")
        except Exception as exc:
            return BifimedFetchResult(status="error", error=str(exc)[:200])

        data = parse_bifimed_detail_html(html, requested_cn=cn)
        if data is None:
            return BifimedFetchResult(status="not_found", raw_payload={"html": html})
        return BifimedFetchResult(status="ok", data=data, raw_payload={"html": html})
