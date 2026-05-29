from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.admin_security import require_admin_api_key
from app.core.database import get_db
from app.models.bifimed_cache import BifimedCache
from app.models.import_batch import ImportBatch
from app.services.bifimed_sync_service import sync_bifimed_cn, sync_import_batch
from app.services.normalization_service import NormalizationError, normalize_cn_or_raise

router = APIRouter(
    prefix="/bifimed", tags=["bifimed"], dependencies=[Depends(require_admin_api_key)]
)


@router.post("/sync/import-batch/{batch_id}")
def sync_bifimed_import_batch_endpoint(
    batch_id: UUID, force: bool = False, db: Session = Depends(get_db)
):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    return sync_import_batch(db, batch_id, force=force)


@router.post("/sync/{cn}")
def sync_bifimed_cn_endpoint(
    cn: str, force: bool = False, db: Session = Depends(get_db)
):
    try:
        row = sync_bifimed_cn(db, cn, force=force)
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "cn": row.cn,
        "sync_status": row.sync_status,
        "situacion_financiacion": row.situacion_financiacion,
        "estado_nomenclator": row.estado_nomenclator,
    }


@router.get("/cache/{cn}")
def get_bifimed_cache(cn: str, db: Session = Depends(get_db)):
    try:
        cn_norm = normalize_cn_or_raise(cn)
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    row = db.get(BifimedCache, cn_norm)
    if not row:
        raise HTTPException(status_code=404, detail="BIFIMED cache not found")
    return row
