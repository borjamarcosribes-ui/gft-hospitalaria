from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.bifimed_cache import BifimedCache
from app.services.bifimed_sync_service import sync_bifimed_cn
from app.services.normalization_service import NormalizationError, normalize_cn

router = APIRouter(prefix="/bifimed", tags=["bifimed"])


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
        cn_norm = normalize_cn(cn)
    except NormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    row = db.get(BifimedCache, cn_norm)
    if not row:
        raise HTTPException(status_code=404, detail="BIFIMED cache not found")
    return row
