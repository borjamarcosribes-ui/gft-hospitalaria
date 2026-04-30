import uuid
from datetime import datetime
from sqlalchemy import Uuid, String, Integer, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ImportRowStaging(Base):
    __tablename__ = "import_row_staging"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("import_batch.id"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cn_raw: Mapped[str | None] = mapped_column(Text)
    cn_normalized: Mapped[str | None] = mapped_column(String(32))
    observaciones_revision_raw: Mapped[str | None] = mapped_column(Text)
    estado_editorial_raw: Mapped[str | None] = mapped_column(Text)
    nemonico_raw: Mapped[str | None] = mapped_column(Text)
    restricciones_hospitalarias_raw: Mapped[str | None] = mapped_column(Text)
    observaciones_internas_raw: Mapped[str | None] = mapped_column(Text)
    comentario_revision_raw: Mapped[str | None] = mapped_column(Text)
    revisado_por_raw: Mapped[str | None] = mapped_column(Text)
    fecha_revision_raw: Mapped[str | None] = mapped_column(Text)
    estado_gft: Mapped[str] = mapped_column(String(32), nullable=False)
    estado_editorial: Mapped[str | None] = mapped_column(String(32))
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    validation_warnings: Mapped[list] = mapped_column(JSON, default=list)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    batch = relationship("ImportBatch", back_populates="rows")
