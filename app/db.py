from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

_settings = get_settings()
_url = _settings.database_url

if _url.startswith("sqlite"):
    _kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if ":memory:" in _url:
        _kwargs["poolclass"] = StaticPool
    engine = create_engine(_url, **_kwargs)
else:
    engine = create_engine(_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401  (registra os modelos)

    if _settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
