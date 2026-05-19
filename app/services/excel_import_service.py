from datetime import datetime
from io import BytesIO
import pandas as pd
from sqlalchemy.orm import Session
from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging
from app.services.gft_excel_dry_run_service import (
    build_gft_excel_column_mapping,
    _validate_header_row,
    _validate_sheet_name,
)
from app.services.normalization_service import (
    normalize_cn,
    classify_observaciones_revision,
    normalize_estado_editorial,
    NormalizationError,
)


def _safe_value(row, key):
    value = row.get(key)
    return None if pd.isna(value) else value


def process_excel_upload(
    db: Session,
    file_bytes: bytes,
    filename: str,
    sheet_name: str | int | None = None,
    header_row: int | None = None,
    default_estado_editorial: str | None = None,
):
    batch = ImportBatch(filename=filename, status="uploaded")
    db.add(batch)
    db.flush()
    try:
        batch.status = "processing"
        batch.started_at = datetime.utcnow()
        excel = pd.ExcelFile(BytesIO(file_bytes))
        selected_sheet = _validate_sheet_name(excel, sheet_name)
        selected_header_row = _validate_header_row(header_row)
        try:
            df = pd.read_excel(excel, sheet_name=selected_sheet, dtype=str, header=selected_header_row - 1)
        except ValueError as exc:
            raise ValueError(f"Fila de encabezado inválida ({selected_header_row}): {exc}") from exc
        column_mapping, missing, _ = build_gft_excel_column_mapping(df.columns)
        estado_editorial_column = column_mapping.get("estado_editorial")

        normalized_default_estado_editorial = None
        if default_estado_editorial is not None:
            normalized_default_estado_editorial = normalize_estado_editorial(default_estado_editorial)

        if estado_editorial_column is None and normalized_default_estado_editorial is None:
            missing = [*missing, "Estado editorial"]

        if missing:
            raise ValueError(f"Columnas obligatorias ausentes: {missing}")

        cn_column = column_mapping["cn"]
        observaciones_column = column_mapping["observaciones_revision"]

        batch.total_rows = len(df)
        for idx, row in df.iterrows():
            errors, warnings = [], []
            cn_raw = _safe_value(row, cn_column)
            try:
                cn = normalize_cn(cn_raw)
            except Exception as exc:
                cn = None
                errors.append(str(exc))

            observaciones_revision = _safe_value(row, observaciones_column)
            estado_gft = classify_observaciones_revision(observaciones_revision)
            estado_editorial_raw = _safe_value(row, estado_editorial_column) if estado_editorial_column else normalized_default_estado_editorial
            try:
                estado_editorial = normalize_estado_editorial(estado_editorial_raw)
            except NormalizationError as exc:
                estado_editorial = None
                errors.append(str(exc))

            staging = ImportRowStaging(
                batch_id=batch.id,
                row_number=idx + selected_header_row + 1,
                cn_raw=cn_raw,
                cn_normalized=cn,
                observaciones_revision_raw=observaciones_revision,
                estado_editorial_raw=estado_editorial_raw,
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
