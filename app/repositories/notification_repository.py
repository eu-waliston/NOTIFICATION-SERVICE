from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.audit import AuditLog
from app.models.notification import Notification, NotificationStatus


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, notification: Notification) -> Notification:
        self.db.add(notification)
        self.db.commit()
        return notification

    def find_by_id(self, notification_id: str) -> Notification | None:
        return self.db.get(Notification, notification_id)

    def find_by_idempotency(self, origin_system: str, key: str) -> Notification | None:
        return self.db.scalar(select(Notification).where(
            Notification.origin_system == origin_system, Notification.idempotency_key == key))

    def update_status(
        self, notification: Notification, status: NotificationStatus, error: str | None = None
    ) -> Notification:
        notification.status = status.value
        notification.error_message = error
        if status is NotificationStatus.SENT:
            notification.sent_at = utcnow()
        self.db.commit()
        return notification

    def search(self, status: str | None = None, origin_system: str | None = None, channel: str | None = None,
               recipient: str | None = None, limit: int = 50, offset: int = 0) -> list[Notification]:
        q = select(Notification).order_by(Notification.created_at.desc())
        if status:
            q = q.where(Notification.status == status.upper())
        if origin_system:
            q = q.where(Notification.origin_system == origin_system)
        if channel:
            q = q.where(Notification.channel == channel)
        if recipient:
            q = q.where(Notification.recipient.contains(recipient))
        return list(self.db.scalars(q.limit(limit).offset(offset)))

    def audit_trail(self, notification_id: str) -> list[AuditLog]:
        return list(self.db.scalars(
            select(AuditLog).where(AuditLog.notification_id == notification_id).order_by(AuditLog.id)))
