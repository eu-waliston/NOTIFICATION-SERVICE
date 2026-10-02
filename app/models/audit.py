from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[str] = mapped_column(String(36), index=True)
    origin_system: Mapped[str] = mapped_column(String(100))
    actor: Mapped[str | None] = mapped_column(String(200), nullable=True)  # usuário responsável
    recipient: Mapped[str] = mapped_column(String(320))
    event: Mapped[str] = mapped_column(String(30))
    result: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
