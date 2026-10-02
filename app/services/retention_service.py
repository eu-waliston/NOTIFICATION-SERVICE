from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.audit import AuditLog
from app.models.notification import Notification


def mask_recipient(recipient: str) -> str:
    if "@" in recipient:
        local, domain = recipient.split("@", 1)
        return f"{local[:1]}***@{domain}"
    return f"***{recipient[-4:]}"


def purge(db: Session, days: int, batch: int = 500) -> int:
    """Anonimiza notificações mais antigas que `days` (remove `data` e mascara destinatário).
    O histórico (status, datas, sistema de origem) é preservado para auditoria."""
    if days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total = 0
    while True:
        items = list(db.scalars(
            select(Notification)
            .where(Notification.created_at < cutoff, Notification.anonymized_at.is_(None))
            .limit(batch)
        ))
        if not items:
            return total
        for n in items:
            masked = mask_recipient(n.recipient)
            db.execute(update(AuditLog).where(AuditLog.notification_id == n.id).values(recipient=masked))
            n.recipient, n.data, n.anonymized_at = masked, {}, utcnow()
        db.commit()
        total += len(items)
