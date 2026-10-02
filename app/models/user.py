import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class ApiClient(Base):
    """Sistema corporativo autorizado a usar o serviço (identificado por API Key)."""

    __tablename__ = "api_clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    allowed_channels: Mapped[list] = mapped_column(JSON, default=lambda: ["email"])
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = padrão global
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
