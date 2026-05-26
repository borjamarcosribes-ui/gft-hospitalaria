from __future__ import annotations
import re
from datetime import datetime
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from app.models.cima_medicamento_cache import CimaMedicamentoCache

_NREG = re.compile(r"/(?:ft|p)/([^/]+)/[^/]+_(?:ft|p)\.pdf$", re.IGNORECASE)

def extract_nregistro_from_aemps_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        path = urlparse(url.strip()).path
    except Exception:
        return None
    m = _NREG.search(path)
    if not m:
        return None
    return m.group(1).strip() or None

def seed_cima_from_imported_urls(db: Session, cn: str, ft_url: str | None, prospecto_url: str | None, *, force: bool=False, repair_not_found: bool=False) -> bool:
    nregistro = extract_nregistro_from_aemps_url(ft_url) or extract_nregistro_from_aemps_url(prospecto_url)
    if not nregistro:
        return False
    row = db.get(CimaMedicamentoCache, cn)
    if row and row.sync_status == 'ok' and not force:
        return False
    if row and row.sync_status == 'not_found' and not (repair_not_found or force):
        return False
    if row is None:
        row = CimaMedicamentoCache(cn=cn)
        db.add(row)
    row.nregistro = nregistro
    row.url_ficha_tecnica = ft_url or row.url_ficha_tecnica
    row.url_prospecto = prospecto_url or row.url_prospecto
    row.sync_status = 'ok'
    row.sync_error = None
    row.last_synced_at = datetime.utcnow()
    docs = []
    if row.url_ficha_tecnica:
        docs.append({'tipo':'ficha_tecnica','url':row.url_ficha_tecnica})
    if row.url_prospecto:
        docs.append({'tipo':'prospecto','url':row.url_prospecto})
    row.documentos_json = docs
    return True
