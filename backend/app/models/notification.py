from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class Notification(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    ticket_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(32), default="IN_APP")
    is_read: Mapped[bool] = mapped_column(default=False)
    severity: Mapped[str] = mapped_column(String(16), default="INFO")
