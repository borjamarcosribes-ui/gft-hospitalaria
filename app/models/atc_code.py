from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AtcCode(Base):
    __tablename__ = "atc_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    parent_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
