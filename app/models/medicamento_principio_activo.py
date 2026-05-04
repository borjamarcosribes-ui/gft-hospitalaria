import uuid
from sqlalchemy import Uuid, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class MedicamentoPrincipioActivo(Base):
    __tablename__ = "medicamento_principio_activo"
    cn: Mapped[str] = mapped_column(Text, primary_key=True)
    principio_activo_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("principio_activo.id"), primary_key=True)
    orden: Mapped[int] = mapped_column(Integer, default=1)
