from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.gft_estado_presentacion import GFTEstadoPresentacion
from app.models.import_batch import ImportBatch
from app.models.import_row_staging import ImportRowStaging

APPLICABLE_ESTADOS_GFT = {"incluido", "excluido"}


def apply_import_batch(db: Session, batch_id: UUID) -> dict | None:
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        return None

    rows = (
        db.query(ImportRowStaging)
        .filter(ImportRowStaging.batch_id == batch.id)
        .order_by(ImportRowStaging.row_number)
        .all()
    )

    summary = {
        "batch_id": str(batch.id),
        "total_rows": len(rows),
        "applied_rows": 0,
        "skipped_errors": 0,
        "skipped_missing_cn": 0,
        "skipped_pending": 0,
        "skipped_missing_estado_editorial": 0,
    }

    for row in rows:
        if row.validation_errors:
            summary["skipped_errors"] += 1
            continue
        if not row.cn_normalized:
            summary["skipped_missing_cn"] += 1
            continue
        if row.estado_gft not in APPLICABLE_ESTADOS_GFT:
            summary["skipped_pending"] += 1
            continue
        if not row.estado_editorial:
            summary["skipped_missing_estado_editorial"] += 1
            continue

        now = datetime.utcnow()
        target = db.get(GFTEstadoPresentacion, row.cn_normalized)
        if target is None:
            target = GFTEstadoPresentacion(cn=row.cn_normalized)
            db.add(target)

        target.estado_gft = row.estado_gft
        target.estado_editorial = row.estado_editorial
        target.nemonico = row.nemonico_raw
        target.restricciones_hospitalarias = row.restricciones_hospitalarias_raw
        target.observaciones_internas = row.observaciones_internas_raw
        target.comentario_revision = row.comentario_revision_raw
        target.revisado_por = row.revisado_por_raw
        target.last_import_batch_id = batch.id
        target.last_imported_at = now
        target.updated_at = now
        summary["applied_rows"] += 1

    db.commit()
    return summary
