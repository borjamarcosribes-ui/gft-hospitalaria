import uuid
from datetime import datetime
from sqlalchemy import Uuid, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class PrincipioActivo(Base):
    __tablename__ = "principio_activo"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre_normalizado: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    nombre_display: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
