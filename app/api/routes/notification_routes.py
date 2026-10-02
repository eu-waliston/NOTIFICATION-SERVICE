from fastapi import APIRouter, BackgroundTasks, Depends, Header, status
from sqlalchemy.orm import Session

from app.core.rate_limit import rate_limited_client
from app.core.security import get_current_client, get_on_behalf_of
from app.db import get_db
from app.models.user import ApiClient
from app.queue import dispatch
from app.schemas import NotificationCreate, NotificationCreated, NotificationOut
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.post("", response_model=NotificationCreated, status_code=status.HTTP_202_ACCEPTED)
def create_notification(
    payload: NotificationCreate,
    background: BackgroundTasks,
    client: ApiClient = Depends(rate_limited_client),
    actor: str | None = Depends(get_on_behalf_of),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    """Solicita um envio. Com `Idempotency-Key`, repetir a chamada devolve a mesma notificação."""
    notification, created = NotificationService(db).create(client, payload, actor, idempotency_key)
    if created:
        dispatch(notification.id, notification.priority, background)
    return NotificationCreated(id=notification.id, status=notification.status)


@router.get("/{notification_id}", response_model=NotificationOut)
def get_notification_status(
    notification_id: str,
    client: ApiClient = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    return NotificationService(db).get(client, notification_id)
