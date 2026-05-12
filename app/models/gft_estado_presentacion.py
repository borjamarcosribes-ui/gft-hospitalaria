from datetime import datetime, date
import uuid
from sqlalchemy import Uuid, String, DateTime, Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class GFTEstadoPresentacion(Base):
    __tablename__ = "gft_estado_presentacion"
    cn: Mapped[str] = mapped_column(String(32), primary_key=True)
    estado_gft: Mapped[str] = mapped_column(String(32), nullable=False)
    estado_editorial: Mapped[str] = mapped_column(String(32), nullable=False)
    nemonico: Mapped[str | None] = mapped_column(Text)
    restricciones_hospitalarias: Mapped[str | None] = mapped_column(Text)
    ajuste_insuficiencia_renal: Mapped[str | None] = mapped_column(Text)
    ajuste_insuficiencia_hepatica: Mapped[str | None] = mapped_column(Text)
    precauciones_embarazo: Mapped[str | None] = mapped_column(Text)
    precauciones_lactancia: Mapped[str | None] = mapped_column(Text)
    observaciones_internas: Mapped[str | None] = mapped_column(Text)
    comentario_revision: Mapped[str | None] = mapped_column(Text)
    revisado_por: Mapped[str | None] = mapped_column(Text)
    fecha_revision: Mapped[date | None] = mapped_column(Date)
    last_import_batch_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("import_batch.id"))
    last_imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
