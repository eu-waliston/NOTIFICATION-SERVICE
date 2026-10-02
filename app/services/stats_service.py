from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.notification import Notification


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def evaluate_alert(sent: int, failed: int, hours: int) -> dict:
    """Regra de detecção de falhas: taxa de falhas >= limiar com volume mínimo de envios finalizados."""
    s = get_settings()
    finished = sent + failed
    rate = (failed / finished) if finished else 0.0
    active = finished >= s.failure_alert_min_events and rate >= s.failure_alert_threshold
    return {
        "active": active,
        "failure_rate": round(rate, 4),
        "threshold": s.failure_alert_threshold,
        "message": (f"Taxa de falhas de {rate:.0%} nas últimas {hours}h "
                    f"({failed} de {finished} envios finalizados).") if active else None,
    }


class StatsService:
    def __init__(self, db: Session):
        self.db = db

    def summary(self, hours: int = 24) -> dict:
        s = get_settings()
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = self.db.execute(
            select(Notification.created_at, Notification.status, Notification.channel,
                   Notification.origin_system, Notification.error_message)
            .where(Notification.created_at >= since)
            .limit(100_000)
        ).all()

        totals = Counter(r.status for r in rows)
        by_channel: dict = defaultdict(lambda: Counter())
        by_system: dict = defaultdict(lambda: Counter())
        errors: Counter = Counter()
        step = timedelta(hours=1) if hours <= 48 else timedelta(days=1)
        timeline: dict = defaultdict(lambda: Counter())

        for r in rows:
            by_channel[r.channel][r.status] += 1
            by_system[r.origin_system][r.status] += 1
            ts = _utc(r.created_at)
            bucket = ts.replace(minute=0, second=0, microsecond=0)
            if step.days:
                bucket = bucket.replace(hour=0)
            timeline[bucket.isoformat()][r.status] += 1
            if r.status == "FAILED" and r.error_message:
                errors[r.error_message[:90]] += 1

        def pack(c: Counter) -> dict:
            return {"total": sum(c.values()), "sent": c["SENT"], "failed": c["FAILED"], "processing": c["PROCESSING"]}

        sent, failed = totals["SENT"], totals["FAILED"]
        finished = sent + failed
        return {
            "window_hours": hours,
            **pack(totals),
            "success_rate": round(sent / finished, 4) if finished else None,
            "by_channel": {k: pack(v) for k, v in sorted(by_channel.items())},
            "by_system": {k: pack(v) for k, v in sorted(by_system.items())},
            "timeline": [{"bucket": k, **pack(v)} for k, v in sorted(timeline.items())],
            "top_errors": [{"error": e, "count": n} for e, n in errors.most_common(5)],
            "alert": evaluate_alert(sent, failed, hours),
        }
