from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.admin_security import require_admin_api_key
from app.core.database import get_db
from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging
from app.services.excel_import_service import process_excel_upload
from app.services.import_apply_service import apply_import_batch
from app.services.import_summary_service import summarize_import_batch
from app.services.gft_excel_dry_run_service import dry_run_gft_excel

router = APIRouter(
    prefix="/imports", tags=["imports"], dependencies=[Depends(require_admin_api_key)]
)


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
async def import_excel(
    file: UploadFile = File(...),
    sheet_name: str | None = Form(None),
    header_row: int | None = Form(None),
    db: Session = Depends(get_db),
):
    content = await file.read()
    batch = process_excel_upload(
        db,
        content,
        file.filename,
        sheet_name=_parse_sheet_name(sheet_name),
        header_row=header_row,
    )
    return {
        "batch_id": str(batch.id),
        "status": batch.status,
        "total_rows": batch.total_rows,
        "processed_rows": batch.processed_rows,
        "ok_rows": batch.ok_rows,
        "error_rows": batch.error_rows,
        "error_summary": batch.error_summary,
    }


@router.post('/excel/dry-run')
async def dry_run_import_excel(
    file: UploadFile = File(...),
    sheet_name: str | None = Form(None),
    header_row: int | None = Form(None),
):
    try:
        content = await file.read()
        result = dry_run_gft_excel(
            content,
            filename=file.filename,
            sheet_name=_parse_sheet_name(sheet_name),
            header_row=header_row,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo validar el Excel: {exc}") from exc

    return result.to_dict()


@router.post('/{batch_id}/apply')
def apply_import(batch_id: UUID, db: Session = Depends(get_db)):
    result = apply_import_batch(db, batch_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Batch no encontrado")
    return result


@router.get('/{batch_id}/summary')
def summarize_import(batch_id: UUID, db: Session = Depends(get_db)):
    result = summarize_import_batch(db, batch_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Batch no encontrado")
    return result


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
