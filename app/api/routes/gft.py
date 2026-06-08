from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.gft import (
    GFTAtcCatalogResponse,
    GFTAtcIndexResponse,
    GFTListResponse,
    GFTMedicamentoDetail,
    GFTPrincipioActivoIndexResponse,
)
from app.services.atc_catalog_service import get_atc_catalog
from app.services.gft_pdf_binary_service import GFTPDFRenderingError, render_gft_pdf_bytes
from app.services.gft_pdf_cache_service import (
    PDF_CACHE_FILENAME,
    get_or_render_cached_gft_pdf_bytes,
)
from app.services.gft_pdf_export_service import build_gft_pdf_export_data
from app.services.gft_pdf_html_render_service import render_gft_pdf_html
from app.services.gft_canonical_payload_service import audit_gft_coverage, build_gft_canonical_payload
from app.services.gft_query_service import (
    get_medicamento_by_cn,
    list_atc_index,
    list_medicamentos,
    list_principios_activos_index,
)

router = APIRouter(prefix="/gft", tags=["gft"])


@router.get("/export/html")
def gft_export_html(mode: str = Query(default="narrative"), db: Session = Depends(get_db)):
    if mode not in {"narrative", "table", "full", "compact"}:
        raise HTTPException(status_code=400, detail="Invalid mode. Allowed values: narrative, table, full, compact.")
    export_data = build_gft_pdf_export_data(db, mode=mode)
    html = render_gft_pdf_html(export_data, mode=mode)
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/export/pdf")
def gft_export_pdf(mode: str = Query(default="narrative"), db: Session = Depends(get_db)):
    if mode not in {"narrative", "table", "full", "compact"}:
        raise HTTPException(status_code=400, detail="Invalid mode. Allowed values: narrative, table, full, compact.")
    export_data = build_gft_pdf_export_data(db, mode=mode)
    try:
        pdf_bytes = get_or_render_cached_gft_pdf_bytes(
            export_data,
            mode=mode,
            html_renderer=render_gft_pdf_html,
            pdf_renderer=render_gft_pdf_bytes,
            db=db,
        )
    except GFTPDFRenderingError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "PDF rendering is unavailable. Use /gft/export/html or install "
                "PDF rendering dependencies."
            ),
        ) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{PDF_CACHE_FILENAME}"'},
    )


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


@router.get("/atc/catalog", response_model=GFTAtcCatalogResponse)
def gft_atc_catalog(db: Session = Depends(get_db)):
    return {"items": get_atc_catalog(db)}


@router.get("/principios-activos", response_model=GFTPrincipioActivoIndexResponse)
def gft_principios_activos_index(db: Session = Depends(get_db)):
    return list_principios_activos_index(db)


@router.get("/audit/coverage")
def gft_audit_coverage(db: Session = Depends(get_db)):
    return audit_gft_coverage(db)


@router.get("/medicamentos/{cn}/canonical")
def gft_get_medicamento_canonical(cn: str, db: Session = Depends(get_db)):
    result = build_gft_canonical_payload(db, cn)
    if result is None:
        raise HTTPException(status_code=404, detail="GFT medicamento not found")
    return result


@router.get("/medicamentos/{cn}", response_model=GFTMedicamentoDetail)
def gft_get_medicamento(cn: str, db: Session = Depends(get_db)):
    result = get_medicamento_by_cn(db, cn)
    if result is None:
        raise HTTPException(status_code=404, detail="GFT medicamento not found")
    canonical = build_gft_canonical_payload(db, cn)
    if canonical is not None:
        result["canonical_payload"] = canonical
    return result
