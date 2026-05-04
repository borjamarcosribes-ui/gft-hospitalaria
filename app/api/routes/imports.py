from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging
from app.services.excel_import_service import process_excel_upload

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post('/excel')
async def import_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    batch = process_excel_upload(db, content, file.filename)
    return {
        "batch_id": str(batch.id),
        "status": batch.status,
        "total_rows": batch.total_rows,
        "processed_rows": batch.processed_rows,
        "ok_rows": batch.ok_rows,
        "error_rows": batch.error_rows,
    }


@router.get('/{batch_id}')
def get_batch(batch_id: UUID, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch no encontrado")
    return batch


@router.get('/{batch_id}/rows')
def get_batch_rows(batch_id: UUID, limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    rows = (
        db.query(ImportRowStaging)
        .filter(ImportRowStaging.batch_id == batch_id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows
