from datetime import datetime

from sqlalchemy.orm import Session

from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.import_row_staging import ImportRowStaging
from app.services.cima_segmented_client import CimaSegmentedClient


def _has_text(value) -> bool:
    return value is not None and str(value).strip() != ""


def sync_cima_segmented_section(
    db: Session,
    nregistro: str,
    tipo_documento: int = 1,
    seccion: str = "4.1",
    cn: str | None = None,
    force: bool = False,
    client: CimaSegmentedClient | None = None,
) -> CimaFichaTecnicaCache:
    if not _has_text(nregistro):
        raise ValueError("nregistro obligatorio")
    if tipo_documento is None:
        raise ValueError("tipo_documento obligatorio")
    if not _has_text(seccion):
        raise ValueError("seccion obligatoria")

    row = (
        db.query(CimaFichaTecnicaCache)
        .filter(
            CimaFichaTecnicaCache.nregistro == nregistro,
            CimaFichaTecnicaCache.tipo_documento == tipo_documento,
            CimaFichaTecnicaCache.seccion == seccion,
        )
        .one_or_none()
    )

    if row and not force:
        return row

    if row is None:
        row = CimaFichaTecnicaCache(
            nregistro=nregistro,
            tipo_documento=tipo_documento,
            seccion=seccion,
            cn=cn,
            titulo=seccion,
            sync_status="not_synced",
        )
        db.add(row)
    elif cn is not None:
        row.cn = cn

    segmented_client = client or CimaSegmentedClient()
    result = segmented_client.get_section_content(
        nregistro=nregistro,
        tipo_documento=tipo_documento,
        seccion=seccion,
    )

    if result.status == "ok":
        data = result.data or {}
        row.sync_status = "ok"
        row.sync_error = None
        row.titulo = data.get("titulo") or seccion
        row.contenido_html = data.get("contenido_html")
        row.contenido_texto = data.get("contenido_texto")
        row.raw_data = result.raw_payload
        if cn is not None:
            row.cn = cn
    elif result.status in {"not_found", "not_segmented", "section_unavailable"}:
        row.sync_status = result.status
        row.sync_error = result.error
        row.raw_data = result.raw_payload
    else:
        row.sync_status = "error"
        row.sync_error = result.error or "Error desconocido"
        row.raw_data = result.raw_payload

    row.last_synced_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def sync_import_batch_segmented_sections(
    db: Session,
    batch_id,
    tipo_documento: int = 1,
    seccion: str = "4.1",
    force: bool = False,
) -> dict:
    rows = db.query(ImportRowStaging).filter(ImportRowStaging.batch_id == batch_id).all()
    cn_set = set()
    nregistro_map = {}
    result = {
        "batch_id": str(batch_id),
        "tipo_documento": tipo_documento,
        "seccion": seccion,
        "total_rows": len(rows),
        "eligible_cn": 0,
        "total_cn": 0,
        "eligible_nregistro": 0,
        "total_nregistro": 0,
        "ok": 0,
        "not_found": 0,
        "not_segmented": 0,
        "section_unavailable": 0,
        "error": 0,
        "skipped_errors": 0,
        "skipped_missing_cn": 0,
        "skipped_pending": 0,
        "skipped_excluded": 0,
        "skipped_missing_estado_editorial": 0,
        "skipped_missing_cima_cache": 0,
        "skipped_cima_cache_not_ok": 0,
        "skipped_missing_nregistro": 0,
        "deduplicated_rows": 0,
        "deduplicated_nregistro": 0,
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

        cn = str(row.cn_normalized).strip()
        if cn in cn_set:
            result["deduplicated_rows"] += 1
        else:
            cn_set.add(cn)

    result["eligible_cn"] = len(cn_set)
    result["total_cn"] = len(cn_set)

    for cn in sorted(cn_set):
        cima_cache = db.get(CimaMedicamentoCache, cn)
        if cima_cache is None:
            result["skipped_missing_cima_cache"] += 1
            continue
        if cima_cache.sync_status != "ok":
            result["skipped_cima_cache_not_ok"] += 1
            continue
        if not _has_text(cima_cache.nregistro):
            result["skipped_missing_nregistro"] += 1
            continue

        nregistro = str(cima_cache.nregistro).strip()
        if nregistro in nregistro_map:
            result["deduplicated_nregistro"] += 1
        else:
            nregistro_map[nregistro] = cn

    result["eligible_nregistro"] = len(nregistro_map)
    result["total_nregistro"] = len(nregistro_map)

    for nregistro in sorted(nregistro_map):
        try:
            row = sync_cima_segmented_section(
                db=db,
                nregistro=nregistro,
                tipo_documento=tipo_documento,
                seccion=seccion,
                cn=nregistro_map[nregistro],
                force=force,
            )
            if row.sync_status in {"ok", "not_found", "not_segmented", "section_unavailable"}:
                result[row.sync_status] += 1
            else:
                result["error"] += 1
        except Exception:
            result["error"] += 1

    return result
