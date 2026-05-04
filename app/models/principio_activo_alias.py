import uuid
from datetime import datetime
from sqlalchemy import Uuid, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class PrincipioActivoAlias(Base):
    __tablename__ = "principio_activo_alias"
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alias_raw: Mapped[str] = mapped_column(Text, nullable=False)
    alias_normalizado: Mapped[str] = mapped_column(Text, nullable=False)
    principio_activo_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("principio_activo.id"), nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
