import logging
import time
from functools import lru_cache

from fastapi import BackgroundTasks

from app.core.config import get_settings
from app.db import SessionLocal

logger = logging.getLogger(__name__)

QUEUES = {
    "high": "notifications:queue:high",
    "normal": "notifications:queue:normal",
    "low": "notifications:queue:low",
}
QUEUE_ORDER = [QUEUES["high"], QUEUES["normal"], QUEUES["low"]]  # BLPOP respeita esta ordem
RETRY_KEY = "notifications:retry"


@lru_cache
def get_redis():
    url = get_settings().redis_url
    if not url:
        return None
    import redis
    return redis.Redis.from_url(url, decode_responses=True)


def priority_of_queue(queue_name: str) -> str:
    return next((p for p, q in QUEUES.items() if q == queue_name), "normal")


def run_inline(notification_id: str) -> None:
    """Fallback sem Redis: processa (com retries) no próprio processo."""
    from app.services.notification_service import NotificationService

    while True:
        with SessionLocal() as db:
            delay = NotificationService(db).process(notification_id)
        if delay is None:
            return
        time.sleep(delay)


def enqueue(r, notification_id: str, priority: str = "normal") -> None:
    r.rpush(QUEUES.get(priority, QUEUES["normal"]), notification_id)


def dispatch(notification_id: str, priority: str, background: BackgroundTasks) -> None:
    r = get_redis()
    if r is not None:
        enqueue(r, notification_id, priority)
    else:
        background.add_task(run_inline, notification_id)


def schedule_retry(r, notification_id: str, delay: float, priority: str = "normal") -> None:
    r.zadd(RETRY_KEY, {f"{priority}|{notification_id}": time.time() + delay})


def promote_due(r) -> None:
    for member in r.zrangebyscore(RETRY_KEY, 0, time.time()):
        if r.zrem(RETRY_KEY, member):  # evita duplicidade entre workers
            priority, _, nid = member.partition("|")
            enqueue(r, nid, priority)
