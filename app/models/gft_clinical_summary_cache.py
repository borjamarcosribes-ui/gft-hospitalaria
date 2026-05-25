from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GftClinicalSummaryCache(Base):
    __tablename__ = "gft_clinical_summary_cache"

    cn: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_status: Mapped[str] = mapped_column(String(32), nullable=False, default="missing_source")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_sections_json: Mapped[list[str] | None] = mapped_column(JSON)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    resumen_general: Mapped[str | None] = mapped_column(Text)
    resumen_indicaciones: Mapped[str | None] = mapped_column(Text)
    resumen_posologia: Mapped[str | None] = mapped_column(Text)
    resumen_ajuste_renal: Mapped[str | None] = mapped_column(Text)
    resumen_ajuste_hepatico: Mapped[str | None] = mapped_column(Text)
    resumen_contraindicaciones: Mapped[str | None] = mapped_column(Text)
    resumen_advertencias: Mapped[str | None] = mapped_column(Text)
    resumen_embarazo: Mapped[str | None] = mapped_column(Text)
    resumen_lactancia: Mapped[str | None] = mapped_column(Text)
    resumen_fuente_json: Mapped[dict | None] = mapped_column(JSON)
    warnings_json: Mapped[list[str] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
