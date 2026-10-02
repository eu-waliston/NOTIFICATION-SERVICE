from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.notification import Notification


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self, notification: Notification, event: str, result: str,
        actor: str | None = None, detail: str | None = None,
    ) -> None:
        self.db.add(AuditLog(
            notification_id=notification.id,
            origin_system=notification.origin_system,
            actor=actor,
            recipient=notification.recipient,
            event=event,
            result=result,
            detail=detail,
        ))
        self.db.commit()
