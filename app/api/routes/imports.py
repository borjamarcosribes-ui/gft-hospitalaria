from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging
from app.services.excel_import_service import process_excel_upload
from app.services.gft_excel_dry_run_service import dry_run_gft_excel

router = APIRouter(prefix="/imports", tags=["imports"])


def _parse_sheet_name(value: str | None) -> str | int | None:
    if value is None:
        return None

    stripped = value.strip()
    if stripped == "":
        return None

    try:
        return int(stripped)
    except ValueError:
        return stripped


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


@router.post('/excel/dry-run')
async def dry_run_import_excel(file: UploadFile = File(...), sheet_name: str | None = None):
    try:
        content = await file.read()
        result = dry_run_gft_excel(
            content,
            filename=file.filename,
            sheet_name=_parse_sheet_name(sheet_name),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo validar el Excel: {exc}") from exc

    return result.to_dict()


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
