from datetime import datetime

from sqlalchemy.orm import Session

from app.models.bifimed_cache import BifimedCache
from app.services.bifimed_client import BifimedClient
from app.services.normalization_service import normalize_cn


def sync_bifimed_cn(db: Session, cn: str, force: bool = False) -> BifimedCache:
    cn_norm = normalize_cn(cn)
    existing = db.get(BifimedCache, cn_norm)

    if existing and not force:
        return existing

    result = BifimedClient().get_by_cn(cn_norm)
    row = existing or BifimedCache(cn=cn_norm)

    if not existing:
        db.add(row)

    if result.status == "ok" and result.data:
        data = result.data
        row.situacion_financiacion = data.get("situacion_financiacion")
        row.condiciones_financiacion_restringidas = data.get(
            "condiciones_financiacion_restringidas"
        )
        row.condiciones_especiales_financiacion = data.get(
            "condiciones_especiales_financiacion"
        )
        row.estado_nomenclator = data.get("estado_nomenclator")
        row.aportacion_usuario = data.get("aportacion_usuario")
        row.subgrupo_atc = data.get("subgrupo_atc")
        row.detalle_financiacion_json = data.get("detalle_financiacion_json")
        row.raw_data = result.raw_payload
        row.sync_status = "ok"
        row.sync_error = None
    elif result.status == "not_found":
        row.sync_status = "not_found"
        row.sync_error = None
    else:
        row.sync_status = "error"
        row.sync_error = (result.error or "bifimed_error")[:200]

    row.last_synced_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row
