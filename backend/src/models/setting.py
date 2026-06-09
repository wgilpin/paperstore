"""Setting ORM model."""

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
