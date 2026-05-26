from datetime import datetime

from sqlalchemy.orm import Session

from app.models.bifimed_cache import BifimedCache
from app.models.import_row_staging import ImportRowStaging
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
        row.indicaciones_autorizadas_json = data.get("indicaciones_autorizadas_json")
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


def _has_text(value) -> bool:
    return value is not None and str(value).strip() != ""


def sync_import_batch(db: Session, batch_id, force: bool = False) -> dict:
    rows = db.query(ImportRowStaging).filter(ImportRowStaging.batch_id == batch_id).all()
    cn_set = set()
    result = {
        "batch_id": str(batch_id),
        "eligible_cn": 0,
        "total_cn": 0,
        "total_rows": len(rows),
        "ok": 0,
        "not_found": 0,
        "error": 0,
        "skipped_errors": 0,
        "skipped_missing_cn": 0,
        "skipped_pending": 0,
        "skipped_excluded": 0,
        "skipped_missing_estado_editorial": 0,
        "deduplicated_rows": 0,
    }

    for row in rows:
        if row.validation_errors:
            result["skipped_errors"] += 1
            continue
        if not _has_text(row.cn_normalized):
            result["skipped_missing_cn"] += 1
            continue
        if row.estado_gft not in ("incluido", "excluido"):
            result["skipped_pending"] += 1
            continue
        if row.estado_gft == "excluido":
            result["skipped_excluded"] += 1
            continue
        if not _has_text(row.estado_editorial):
            result["skipped_missing_estado_editorial"] += 1
            continue

        if row.cn_normalized in cn_set:
            result["deduplicated_rows"] += 1
        else:
            cn_set.add(row.cn_normalized)

    result["eligible_cn"] = len(cn_set)
    result["total_cn"] = len(cn_set)

    for cn in sorted(cn_set):
        try:
            row = sync_bifimed_cn(db, cn, force=force)
            if row.sync_status == "ok":
                result["ok"] += 1
            elif row.sync_status == "not_found":
                result["not_found"] += 1
            else:
                result["error"] += 1
        except Exception:
            result["error"] += 1

    return result
