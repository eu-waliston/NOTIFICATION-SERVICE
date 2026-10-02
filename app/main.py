import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import (admin_routes, ai_routes, dashboard_routes, email_routes, health_routes,
                            notification_routes)
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db import SessionLocal, init_db
from app.services import retention_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _purge_once(days: int) -> None:
    with SessionLocal() as db:
        n = retention_service.purge(db, days)
    if n:
        logger.info("Retenção: %d notificações anonimizadas.", n)


async def _retention_loop(days: int) -> None:
    while True:
        try:
            await asyncio.to_thread(_purge_once, days)
        except Exception:
            logger.exception("Falha na rotina de retenção")
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    s = get_settings()
    task = None
    # Com Redis, quem executa a retenção é o worker; sem Redis, a própria API.
    if s.data_retention_days > 0 and not s.redis_url:
        task = asyncio.create_task(_retention_loop(s.data_retention_days))
    yield
    if task:
        task.cancel()


app = FastAPI(
    title=get_settings().app_name,
    version="2.0.0",
    description="Serviço centralizado de notificações corporativas (email, Teams, WhatsApp, SMS).",
    lifespan=lifespan,
)
register_exception_handlers(app)
app.include_router(health_routes.router)
app.include_router(notification_routes.router)
app.include_router(email_routes.router)
app.include_router(admin_routes.router)
app.include_router(ai_routes.router)
app.include_router(dashboard_routes.router)
