import uuid
from datetime import datetime, date
from sqlalchemy import Uuid, String, DateTime, Date, Integer, Text, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CimaFichaTecnicaCache(Base):
    __tablename__ = "cima_ficha_tecnica_cache"
    __table_args__ = (
        UniqueConstraint(
            "nregistro",
            "tipo_documento",
            "seccion",
            name="uq_cima_ficha_tecnica_cache_nregistro_tipo_seccion",
        ),
        Index(
            "ix_cima_ficha_tecnica_cache_nregistro_tipo_seccion",
            "nregistro",
            "tipo_documento",
            "seccion",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cn: Mapped[str | None] = mapped_column(Text)
    nregistro: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_documento: Mapped[int] = mapped_column(Integer, nullable=False)
    seccion: Mapped[str] = mapped_column(Text, nullable=False)
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    contenido_html: Mapped[str | None] = mapped_column(Text)
    contenido_texto: Mapped[str | None] = mapped_column(Text)
    fecha_documento: Mapped[date | None] = mapped_column(Date)
    raw_data: Mapped[dict | None] = mapped_column(JSON)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_synced")
    sync_error: Mapped[str | None] = mapped_column(Text)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
