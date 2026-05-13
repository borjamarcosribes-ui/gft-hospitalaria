from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.enums import ESTADO_EDITORIAL_VALUES, ESTADO_GFT_VALUES
from app.models.gft_estado_presentacion import GFTEstadoPresentacion


class GFTStateValidationError(ValueError):
    pass


def update_gft_publication_state(
    db: Session,
    cn: str,
    estado_gft: str | None = None,
    estado_editorial: str | None = None,
    comentario_revision: str | None = None,
    revisado_por: str | None = None,
) -> GFTEstadoPresentacion | None:
    normalized_cn = cn.strip() if cn is not None else ""
    if not normalized_cn:
        raise GFTStateValidationError("CN obligatorio")

    if estado_gft is None and estado_editorial is None:
        raise GFTStateValidationError("No hay estados para actualizar")

    normalized_estado_gft = None
    if estado_gft is not None:
        normalized_estado_gft = estado_gft.strip()
        if not normalized_estado_gft:
            raise GFTStateValidationError("estado_gft no puede estar vacío")
        if normalized_estado_gft not in ESTADO_GFT_VALUES:
            raise GFTStateValidationError("estado_gft inválido")

    normalized_estado_editorial = None
    if estado_editorial is not None:
        normalized_estado_editorial = estado_editorial.strip()
        if not normalized_estado_editorial:
            raise GFTStateValidationError("estado_editorial no puede estar vacío")
        if normalized_estado_editorial not in ESTADO_EDITORIAL_VALUES:
            raise GFTStateValidationError("estado_editorial inválido")

    row = db.get(GFTEstadoPresentacion, normalized_cn)
    if row is None:
        return None

    effective_estado_gft = (
        normalized_estado_gft if estado_gft is not None else row.estado_gft
    )
    effective_estado_editorial = (
        normalized_estado_editorial
        if estado_editorial is not None
        else row.estado_editorial
    )

    if (
        effective_estado_editorial == "publicado"
        and effective_estado_gft != "incluido"
    ):
        raise GFTStateValidationError("Solo se puede publicar un medicamento incluido")

    if (
        effective_estado_gft != "incluido"
        and effective_estado_editorial == "publicado"
    ):
        raise GFTStateValidationError("Solo se puede publicar un medicamento incluido")

    if normalized_estado_gft is not None:
        row.estado_gft = normalized_estado_gft
    if normalized_estado_editorial is not None:
        row.estado_editorial = normalized_estado_editorial

    if comentario_revision is not None:
        normalized_comentario_revision = comentario_revision.strip()
        row.comentario_revision = normalized_comentario_revision or None

    normalized_revisado_por = revisado_por.strip() if revisado_por is not None else ""
    if normalized_revisado_por:
        row.revisado_por = normalized_revisado_por
        row.fecha_revision = date.today()

    row.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(row)
    return row
