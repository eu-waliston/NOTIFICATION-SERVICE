"""Worker de envio (todos os canais). Execute: python -m app.workers.email_worker"""
import logging
import signal
import sys
import time

from app.core.config import get_settings
from app.db import SessionLocal, init_db
from app.queue import QUEUE_ORDER, get_redis, priority_of_queue, promote_due, schedule_retry
from app.services import retention_service
from app.services.notification_service import NotificationService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("email_worker")
_running = True
PURGE_EVERY = 3600


def _stop(*_):
    global _running
    _running = False


def _maybe_purge(last: float) -> float:
    days = get_settings().data_retention_days
    if days > 0 and time.time() - last >= PURGE_EVERY:
        with SessionLocal() as db:
            n = retention_service.purge(db, days)
        if n:
            logger.info("Retenção: %d notificações anonimizadas.", n)
        return time.time()
    return last


def main() -> None:
    r = get_redis()
    if r is None:
        logger.error("REDIS_URL não configurada; worker não pode iniciar.")
        sys.exit(1)
    init_db()
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logger.info("Worker iniciado.")
    last_purge = 0.0

    while _running:
        promote_due(r)
        last_purge = _maybe_purge(last_purge)
        item = r.blpop(QUEUE_ORDER, timeout=5)
        if not item:
            continue
        queue_name, notification_id = item
        try:
            with SessionLocal() as db:
                delay = NotificationService(db).process(notification_id)
            if delay is not None:
                schedule_retry(r, notification_id, delay, priority_of_queue(queue_name))
        except Exception:
            logger.exception("Erro inesperado ao processar %s", notification_id)
    logger.info("Worker encerrado.")


if __name__ == "__main__":
    main()
