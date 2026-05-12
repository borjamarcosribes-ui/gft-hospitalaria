from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.gft_estado_presentacion import GFTEstadoPresentacion


ALLOWED_EDITORIAL_FIELDS = {
    "restricciones_hospitalarias",
    "ajuste_insuficiencia_renal",
    "ajuste_insuficiencia_hepatica",
    "precauciones_embarazo",
    "precauciones_lactancia",
    "observaciones_internas",
    "comentario_revision",
}


class GFTEditorialValidationError(ValueError):
    pass


def _normalize_editorial_value(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip() if isinstance(value, str) else str(value).strip()
    return normalized or None


def update_gft_editorial_fields(
    db: Session,
    cn: str,
    fields: dict[str, str | None],
    revisado_por: str | None = None,
) -> GFTEstadoPresentacion | None:
    normalized_cn = cn.strip() if cn is not None else ""
    if not normalized_cn:
        raise GFTEditorialValidationError("CN obligatorio")

    if not fields:
        raise GFTEditorialValidationError("No hay campos para actualizar")

    forbidden_fields = sorted(set(fields) - ALLOWED_EDITORIAL_FIELDS)
    if forbidden_fields:
        raise GFTEditorialValidationError(
            f"Campos editoriales no permitidos: {', '.join(forbidden_fields)}"
        )

    row = db.get(GFTEstadoPresentacion, normalized_cn)
    if row is None:
        return None

    for field_name, value in fields.items():
        setattr(row, field_name, _normalize_editorial_value(value))

    row.updated_at = datetime.utcnow()

    normalized_revisado_por = revisado_por.strip() if revisado_por is not None else ""
    if normalized_revisado_por:
        row.revisado_por = normalized_revisado_por
        row.fecha_revision = date.today()

    db.commit()
    db.refresh(row)
    return row
