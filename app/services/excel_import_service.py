from datetime import datetime
from io import BytesIO
import pandas as pd
from sqlalchemy.orm import Session
from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging
from app.services.normalization_service import (
    normalize_cn,
    classify_observaciones_revision,
    normalize_estado_editorial,
    NormalizationError,
)

REQUIRED_COLUMNS = ["CN", "Observaciones revisión", "Estado editorial"]


def _safe_value(row, key):
    value = row.get(key)
    return None if pd.isna(value) else value


def process_excel_upload(db: Session, file_bytes: bytes, filename: str):
    batch = ImportBatch(filename=filename, status="uploaded")
    db.add(batch)
    db.flush()
    try:
        batch.status = "processing"
        batch.started_at = datetime.utcnow()
        df = pd.read_excel(BytesIO(file_bytes), dtype=str)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Columnas obligatorias ausentes: {missing}")

        batch.total_rows = len(df)
        for idx, row in df.iterrows():
            errors, warnings = [], []
            cn_raw = _safe_value(row, "CN")
            try:
                cn = normalize_cn(cn_raw)
            except Exception as exc:
                cn = None
                errors.append(str(exc))

            observaciones_revision = _safe_value(row, "Observaciones revisión")
            estado_gft = classify_observaciones_revision(observaciones_revision)
            try:
                estado_editorial = normalize_estado_editorial(_safe_value(row, "Estado editorial"))
            except NormalizationError as exc:
                estado_editorial = None
                errors.append(str(exc))

            staging = ImportRowStaging(
                batch_id=batch.id,
                row_number=idx + 2,
                cn_raw=cn_raw,
                cn_normalized=cn,
                observaciones_revision_raw=observaciones_revision,
                estado_editorial_raw=_safe_value(row, "Estado editorial"),
                nemonico_raw=_safe_value(row, "Nemónico"),
                restricciones_hospitalarias_raw=_safe_value(row, "Restricciones hospitalarias"),
                observaciones_internas_raw=_safe_value(row, "Observaciones internas GFT"),
                comentario_revision_raw=_safe_value(row, "Comentario revisión"),
                revisado_por_raw=_safe_value(row, "Revisado por"),
                fecha_revision_raw=_safe_value(row, "Fecha revisión"),
                estado_gft=estado_gft,
                estado_editorial=estado_editorial,
                validation_errors=errors,
                validation_warnings=warnings,
                raw_payload={k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()},
            )
            db.add(staging)
            if errors:
                batch.error_rows += 1
            else:
                batch.ok_rows += 1
            batch.processed_rows += 1

        batch.finished_at = datetime.utcnow()
        batch.status = "with_errors" if batch.error_rows else "validated"
    except Exception as exc:
        batch.status = "failed"
        batch.error_summary = {"error": str(exc)}
    db.commit()
    db.refresh(batch)
    return batch
