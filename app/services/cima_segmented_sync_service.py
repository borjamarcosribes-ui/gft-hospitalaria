from datetime import datetime

from sqlalchemy.orm import Session

from app.models.cima_ficha_tecnica_cache import CimaFichaTecnicaCache
from app.services.cima_segmented_client import CimaSegmentedClient


def _has_text(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def sync_cima_segmented_section(
    db: Session,
    nregistro: str,
    tipo_documento: int = 1,
    seccion: str = "4.1",
    cn: str | None = None,
    force: bool = False,
    client: CimaSegmentedClient | None = None,
) -> CimaFichaTecnicaCache:
    if not _has_text(nregistro):
        raise ValueError("nregistro obligatorio")
    if tipo_documento is None:
        raise ValueError("tipo_documento obligatorio")
    if not _has_text(seccion):
        raise ValueError("seccion obligatoria")

    row = (
        db.query(CimaFichaTecnicaCache)
        .filter(
            CimaFichaTecnicaCache.nregistro == nregistro,
            CimaFichaTecnicaCache.tipo_documento == tipo_documento,
            CimaFichaTecnicaCache.seccion == seccion,
        )
        .one_or_none()
    )

    if row and not force:
        return row

    if row is None:
        row = CimaFichaTecnicaCache(
            nregistro=nregistro,
            tipo_documento=tipo_documento,
            seccion=seccion,
            cn=cn,
            titulo=seccion,
            sync_status="not_synced",
        )
        db.add(row)
    elif cn is not None:
        row.cn = cn

    segmented_client = client or CimaSegmentedClient()
    result = segmented_client.get_section_content(
        nregistro=nregistro,
        tipo_documento=tipo_documento,
        seccion=seccion,
    )

    if result.status == "ok":
        data = result.data or {}
        row.sync_status = "ok"
        row.sync_error = None
        row.titulo = data.get("titulo") or seccion
        row.contenido_html = data.get("contenido_html")
        row.contenido_texto = data.get("contenido_texto")
        row.raw_data = result.raw_payload
        if cn is not None:
            row.cn = cn
    elif result.status in {"not_found", "not_segmented", "section_unavailable"}:
        row.sync_status = result.status
        row.sync_error = result.error
        row.raw_data = result.raw_payload
    else:
        row.sync_status = "error"
        row.sync_error = result.error or "Error desconocido"
        row.raw_data = result.raw_payload

    row.last_synced_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row
