from datetime import datetime, date
from sqlalchemy import String, DateTime, Date, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CimaMedicamentoCache(Base):
    __tablename__ = "cima_medicamento_cache"
    cn: Mapped[str] = mapped_column(String(32), primary_key=True)
    nregistro: Mapped[str | None] = mapped_column(String(64))
    nombre: Mapped[str | None] = mapped_column(Text)
    presentacion: Mapped[str | None] = mapped_column(Text)
    forma_farmaceutica: Mapped[str | None] = mapped_column(Text)
    forma_farmaceutica_simplificada: Mapped[str | None] = mapped_column(Text)
    vias_administracion_json: Mapped[dict | None] = mapped_column(JSON)
    atc_json: Mapped[dict | None] = mapped_column(JSON)
    principios_activos_json: Mapped[dict | None] = mapped_column(JSON)
    documentos_json: Mapped[dict | None] = mapped_column(JSON)
    url_ficha_tecnica: Mapped[str | None] = mapped_column(Text)
    url_prospecto: Mapped[str | None] = mapped_column(Text)
    fecha_ficha_tecnica: Mapped[date | None] = mapped_column(Date)
    fecha_prospecto: Mapped[date | None] = mapped_column(Date)
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_implemented")
    sync_error: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
