from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.cima_medicamento_cache import CimaMedicamentoCache
from app.models.import_batch import ImportBatch
from app.services.cima_sync_service import sync_cn, sync_import_batch
from app.services.normalization_service import normalize_cn, NormalizationError

router = APIRouter(prefix="/cima", tags=["cima"])


@router.post('/sync/{cn}')
def sync_cn_endpoint(cn: str, force: bool = False, db: Session = Depends(get_db)):
    row = sync_cn(db, cn, force=force)
    return {
        "cn": row.cn,
        "sync_status": row.sync_status,
        "url_ficha_tecnica": row.url_ficha_tecnica,
        "url_prospecto": row.url_prospecto,
    }


@router.get('/cache/{cn}')
def get_cache(cn: str, db: Session = Depends(get_db)):
    try:
        cn_norm = normalize_cn(cn)
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    row = db.get(CimaMedicamentoCache, cn_norm)
    if not row:
        raise HTTPException(status_code=404, detail="CIMA cache not found")
    return row


@router.post('/sync/import-batch/{batch_id}')
def sync_import_batch_endpoint(batch_id: UUID, force: bool = False, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return sync_import_batch(db, batch_id, force=force)
