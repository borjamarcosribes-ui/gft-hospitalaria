from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging
from app.services.import_apply_service import APPLICABLE_ESTADOS_GFT


def _has_items(value: list | None) -> bool:
    return bool(value)


def summarize_import_batch(db: Session, batch_id: UUID) -> dict | None:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        return None

    rows = (
        db.query(ImportRowStaging)
        .filter(ImportRowStaging.batch_id == batch.id)
        .order_by(ImportRowStaging.row_number)
        .all()
    )

    duplicate_rows_by_cn: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        if row.cn_normalized:
            duplicate_rows_by_cn[row.cn_normalized].append(row.row_number)

    duplicate_cn = [
        {"cn": cn, "rows": row_numbers}
        for cn, row_numbers in sorted(duplicate_rows_by_cn.items())
        if len(row_numbers) > 1
    ]

    summary = {
        "batch_id": str(batch.id),
        "status": batch.status,
        "filename": batch.filename,
        "batch_total_rows": batch.total_rows,
        "staging_total_rows": len(rows),
        "included_rows": 0,
        "excluded_rows": 0,
        "pending_rows": 0,
        "error_rows": 0,
        "warning_rows": 0,
        "applicable_rows": 0,
        "not_applicable_rows": 0,
        "skipped_errors": 0,
        "skipped_missing_cn": 0,
        "skipped_pending": 0,
        "skipped_missing_estado_editorial": 0,
        "duplicate_cn_count": len(duplicate_cn),
        "duplicate_cn": duplicate_cn,
        "pending_items": [],
        "error_items": [],
    }

    for row in rows:
        if row.estado_gft == "incluido":
            summary["included_rows"] += 1
        elif row.estado_gft == "excluido":
            summary["excluded_rows"] += 1
        else:
            summary["pending_rows"] += 1

        if _has_items(row.validation_errors):
            summary["error_rows"] += 1
            summary["error_items"].append(
                {
                    "row_number": row.row_number,
                    "cn_raw": row.cn_raw,
                    "cn": row.cn_normalized,
                    "validation_errors": row.validation_errors,
                }
            )
        if _has_items(row.validation_warnings):
            summary["warning_rows"] += 1

        if not row.cn_normalized:
            summary["skipped_missing_cn"] += 1
        elif _has_items(row.validation_errors):
            summary["skipped_errors"] += 1
        elif row.estado_gft not in APPLICABLE_ESTADOS_GFT:
            summary["skipped_pending"] += 1
            summary["pending_items"].append(
                {
                    "row_number": row.row_number,
                    "cn": row.cn_normalized,
                    "observaciones_revision_raw": row.observaciones_revision_raw,
                    "estado_editorial": row.estado_editorial,
                }
            )
        elif not row.estado_editorial:
            summary["skipped_missing_estado_editorial"] += 1
        else:
            summary["applicable_rows"] += 1

    summary["not_applicable_rows"] = len(rows) - summary["applicable_rows"]
    return summary
