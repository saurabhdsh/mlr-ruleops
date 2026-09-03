from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class IntegrationConfiguration(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "integration_configurations"

    name: Mapped[str] = mapped_column(String(64), unique=True)
    provider: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="NOT_CONFIGURED")
    base_url: Mapped[str] = mapped_column(String(500), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
