from sqlalchemy import String, Text

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin
from sqlalchemy.orm import Mapped, mapped_column


class ConfigurationMatrixRow(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "configuration_matrix"

    config_id: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    market: Mapped[str] = mapped_column(String(16), index=True)
    country: Mapped[str] = mapped_column(String(16), default="")
    language: Mapped[str] = mapped_column(String(16), index=True)
    brand: Mapped[str] = mapped_column(String(64), index=True)
    therapeutic_area: Mapped[str] = mapped_column(String(64), default="")
    string_type: Mapped[str] = mapped_column(String(32), index=True)
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    static_link: Mapped[str] = mapped_column(String(512), default="")
    rule_switch: Mapped[str] = mapped_column(String(16), default="ON")
    additional_params: Mapped[str] = mapped_column(Text, default="{}")
    rule_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
