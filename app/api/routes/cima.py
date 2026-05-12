from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.import_batch import ImportBatch
from app.services.cima_segmented_sync_service import sync_cima_segmented_section
from app.services.cima_sync_service import sync_cn, sync_import_batch
from app.services.normalization_service import normalize_cn, NormalizationError


def _serialize_segmented_cache_row(row: CimaFichaTecnicaCache) -> dict:
    return {
        "nregistro": row.nregistro,
        "tipo_documento": row.tipo_documento,
        "seccion": row.seccion,
        "cn": row.cn,
        "titulo": row.titulo,
        "contenido_html": row.contenido_html,
        "contenido_texto": row.contenido_texto,
        "sync_status": row.sync_status,
        "sync_error": row.sync_error,
        "last_synced_at": row.last_synced_at,
    }


router = APIRouter(prefix="/cima", tags=["cima"])


@router.post("/sync/{cn}")
def sync_cn_endpoint(cn: str, force: bool = False, db: Session = Depends(get_db)):
    row = sync_cn(db, cn, force=force)
    return {
        "cn": row.cn,
        "sync_status": row.sync_status,
        "url_ficha_tecnica": row.url_ficha_tecnica,
        "url_prospecto": row.url_prospecto,
    }


@router.get("/cache/{cn}")
def get_cache(cn: str, db: Session = Depends(get_db)):
    try:
        cn_norm = normalize_cn(cn)
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    row = db.get(CimaMedicamentoCache, cn_norm)
    if not row:
        raise HTTPException(status_code=404, detail="CIMA cache not found")
    return row


@router.post("/sync/import-batch/{batch_id}")
def sync_import_batch_endpoint(batch_id: UUID, force: bool = False, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return sync_import_batch(db, batch_id, force=force)


@router.post("/segmented/sync/{nregistro}")
def sync_segmented_section_endpoint(
    nregistro: str,
    tipo_documento: int = 1,
    seccion: str = "4.1",
    cn: str | None = None,
    force: bool = False,
    db: Session = Depends(get_db),
):
    try:
        row = sync_cima_segmented_section(
            db=db,
            nregistro=nregistro,
            tipo_documento=tipo_documento,
            seccion=seccion,
            cn=cn,
            force=force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _serialize_segmented_cache_row(row)


@router.get("/segmented/cache/{nregistro}")
def get_segmented_cache_endpoint(
    nregistro: str,
    tipo_documento: int = 1,
    seccion: str = "4.1",
    db: Session = Depends(get_db),
):
    row = (
        db.query(CimaFichaTecnicaCache)
        .filter(
            CimaFichaTecnicaCache.nregistro == nregistro,
            CimaFichaTecnicaCache.tipo_documento == tipo_documento,
            CimaFichaTecnicaCache.seccion == seccion,
        )
        .one_or_none()
    )
    if not row:
        raise HTTPException(status_code=404, detail="CIMA segmented cache not found")
    return _serialize_segmented_cache_row(row)
