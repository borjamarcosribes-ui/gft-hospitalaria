from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.gft import GFTAtcIndexResponse, GFTListResponse, GFTMedicamentoDetail
from app.services.gft_query_service import get_medicamento_by_cn, list_atc_index, list_medicamentos

router = APIRouter(prefix="/gft", tags=["gft"])


@router.get("/medicamentos", response_model=GFTListResponse)
def gft_list_medicamentos(
    limit: int = 20,
    offset: int = 0,
    q: str | None = None,
    letra: str | None = None,
    principio_activo: str | None = None,
    atc: str | None = None,
    db: Session = Depends(get_db),
):
    return list_medicamentos(
        db,
        limit=limit,
        offset=offset,
        q=q,
        letra=letra,
        principio_activo=principio_activo,
        atc=atc,
    )


@router.get("/atc", response_model=GFTAtcIndexResponse)
def gft_atc_index(db: Session = Depends(get_db)):
    return list_atc_index(db)


@router.get("/medicamentos/{cn}", response_model=GFTMedicamentoDetail)
def gft_get_medicamento(cn: str, db: Session = Depends(get_db)):
    result = get_medicamento_by_cn(db, cn)
    if result is None:
        raise HTTPException(status_code=404, detail="GFT medicamento not found")
    return result
