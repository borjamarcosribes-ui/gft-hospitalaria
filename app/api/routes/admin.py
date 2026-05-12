from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.admin_security import require_admin_api_key
from app.core.database import get_db
from app.services.gft_editorial_service import (
    GFTEditorialValidationError,
    update_gft_editorial_fields,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class GFTEditorialUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restricciones_hospitalarias: str | None = None
    ajuste_insuficiencia_renal: str | None = None
    ajuste_insuficiencia_hepatica: str | None = None
    precauciones_embarazo: str | None = None
    precauciones_lactancia: str | None = None
    observaciones_internas: str | None = None
    comentario_revision: str | None = None
    revisado_por: str | None = None


class GFTEditorialUpdateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cn: str
    restricciones_hospitalarias: str | None = None
    ajuste_insuficiencia_renal: str | None = None
    ajuste_insuficiencia_hepatica: str | None = None
    precauciones_embarazo: str | None = None
    precauciones_lactancia: str | None = None
    observaciones_internas: str | None = None
    comentario_revision: str | None = None
    revisado_por: str | None = None
    fecha_revision: date | None = None
    updated_at: datetime | None = None


@router.get("/health")
def admin_health(_: None = Depends(require_admin_api_key)):
    return {"status": "ok"}


@router.patch("/gft/medicamentos/{cn}/editorial", response_model=GFTEditorialUpdateResponse)
def update_gft_medicamento_editorial(
    cn: str,
    body: GFTEditorialUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
):
    payload = body.model_dump(exclude_unset=True)
    revisado_por = payload.pop("revisado_por", None)

    try:
        result = update_gft_editorial_fields(
            db,
            cn=cn,
            fields=payload,
            revisado_por=revisado_por,
        )
    except GFTEditorialValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Medicamento GFT no encontrado")

    return result
