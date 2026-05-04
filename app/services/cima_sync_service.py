from datetime import datetime
from sqlalchemy.orm import Session
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.import_row_staging import ImportRowStaging
from app.services.cima_client import CimaClient
from app.services.normalization_service import normalize_cn


def sync_cn(db: Session, cn: str, force: bool = False):
    cn_norm = normalize_cn(cn)
    existing = db.get(CimaMedicamentoCache, cn_norm)

    if existing and not force:
        return existing

    result = CimaClient().get_by_cn(cn_norm)
    row = existing or CimaMedicamentoCache(cn=cn_norm)

    if not existing:
        db.add(row)

    if result.status == "ok" and result.data:
        d = result.data
        row.nregistro = d.get("nregistro")
        row.nombre = d.get("nombre")
        row.presentacion = d.get("presentacion")
        row.forma_farmaceutica = d.get("forma_farmaceutica")
        row.forma_farmaceutica_simplificada = d.get("forma_farmaceutica_simplificada")
        row.vias_administracion_json = d.get("vias_administracion_json")
        row.atc_json = d.get("atc_json")
        row.principios_activos_json = d.get("principios_activos_json")
        row.documentos_json = d.get("documentos_json")
        row.url_ficha_tecnica = d.get("url_ficha_tecnica")
        row.url_prospecto = d.get("url_prospecto")
        row.fecha_ficha_tecnica = d.get("fecha_ficha_tecnica")
        row.fecha_prospecto = d.get("fecha_prospecto")
        row.raw_data = result.raw_payload
        row.sync_status = "ok"
        row.sync_error = None
    elif result.status == "not_found":
        row.sync_status = "not_found"
        row.sync_error = None
    else:
        row.sync_status = "error"
        row.sync_error = (result.error or "cima_error")[:200]

    row.last_synced_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def sync_import_batch(db: Session, batch_id, force: bool = False):
    rows = db.query(ImportRowStaging).filter(ImportRowStaging.batch_id == batch_id).all()
    cn_set = set()

    for row in rows:
        if not row.cn_normalized:
            continue
        if row.estado_gft != "incluido":
            continue
        if row.validation_errors:
            continue
        cn_set.add(row.cn_normalized)

    result = {
        "batch_id": str(batch_id),
        "total_cn": len(cn_set),
        "ok": 0,
        "not_found": 0,
        "error": 0,
        "skipped": 0,
    }

    for cn in sorted(cn_set):
        try:
            row = sync_cn(db, cn, force=force)
            if row.sync_status == "ok":
                result["ok"] += 1
            elif row.sync_status == "not_found":
                result["not_found"] += 1
            else:
                result["error"] += 1
        except Exception:
            result["error"] += 1

    return result
