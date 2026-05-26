from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class BifimedCache(Base):
    __tablename__ = "bifimed_cache"
    cn: Mapped[str] = mapped_column(String(32), primary_key=True)
    situacion_financiacion: Mapped[str | None] = mapped_column(Text)
    condiciones_financiacion_restringidas: Mapped[str | None] = mapped_column(Text)
    condiciones_especiales_financiacion: Mapped[str | None] = mapped_column(Text)
    estado_nomenclator: Mapped[str | None] = mapped_column(Text)
    aportacion_usuario: Mapped[str | None] = mapped_column(Text)
    subgrupo_atc: Mapped[str | None] = mapped_column(Text)
    detalle_financiacion_json: Mapped[dict | None] = mapped_column(JSON)
    indicaciones_autorizadas_json: Mapped[list[dict] | None] = mapped_column(JSON)
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_implemented")
    sync_error: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
