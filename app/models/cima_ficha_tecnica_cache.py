import uuid
from datetime import datetime, date
from sqlalchemy import Uuid, String, DateTime, Date, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CimaFichaTecnicaCache(Base):
    __tablename__ = "cima_ficha_tecnica_cache"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cn: Mapped[str | None] = mapped_column(Text)
    nregistro: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_documento: Mapped[int] = mapped_column(Integer, nullable=False)
    seccion: Mapped[str] = mapped_column(Text, nullable=False)
    titulo: Mapped[str] = mapped_column(Text, nullable=False)
    contenido_html: Mapped[str | None] = mapped_column(Text)
    contenido_texto: Mapped[str | None] = mapped_column(Text)
    fecha_documento: Mapped[date | None] = mapped_column(Date)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
