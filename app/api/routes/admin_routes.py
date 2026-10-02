from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from jinja2 import TemplateSyntaxError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import Conflict, NotFoundError, ValidationFailed
from app.core.security import generate_api_key, hash_api_key, require_admin
from app.db import get_db
from app.models.template import Template
from app.models.user import ApiClient
from app.queue import dispatch
from app.repositories.notification_repository import NotificationRepository
from app.repositories.template_repository import TemplateRepository
from app.schemas import (AuditOut, ClientCreated, ClientIn, ClientOut, ClientUpdate, NotificationOut,
                         TemplateIn, TemplateOut)
from app.services import retention_service
from app.services.notification_service import NotificationService
from app.services.stats_service import StatsService
from app.services.template_service import find_variables

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _validate_template(body: TemplateIn) -> None:
    try:
        used = set(find_variables(body.html_content, body.subject))
    except TemplateSyntaxError as exc:
        raise ValidationFailed(f"Sintaxe Jinja2 inválida: {exc}") from exc
    undeclared = used - set(body.variables)
    if undeclared:
        raise ValidationFailed(f"Variáveis usadas mas não declaradas em 'variables': {', '.join(sorted(undeclared))}")
    if body.external_template_name and body.channel != "whatsapp":
        raise ValidationFailed("external_template_name só é válido para o canal whatsapp.")


# ---------------- Templates ----------------
@router.post("/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(body: TemplateIn, db: Session = Depends(get_db)):
    repo = TemplateRepository(db)
    if repo.get_by_name(body.name):
        raise Conflict(f"Template '{body.name}' já existe.")
    _validate_template(body)
    return repo.save(Template(**body.model_dump()))


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    return TemplateRepository(db).list()


@router.put("/templates/{name}", response_model=TemplateOut)
def update_template(name: str, body: TemplateIn, db: Session = Depends(get_db)):
    repo = TemplateRepository(db)
    tpl = repo.get_by_name(name)
    if tpl is None:
        raise NotFoundError(f"Template '{name}' não encontrado.")
    if body.name != name and repo.get_by_name(body.name):
        raise Conflict(f"Template '{body.name}' já existe.")
    _validate_template(body)
    for k, v in body.model_dump().items():
        setattr(tpl, k, v)
    return repo.save(tpl)


@router.delete("/templates/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(name: str, db: Session = Depends(get_db)):
    repo = TemplateRepository(db)
    tpl = repo.get_by_name(name)
    if tpl is None:
        raise NotFoundError(f"Template '{name}' não encontrado.")
    repo.delete(tpl)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------- Sistemas clientes (controle de acesso) ----------------
def _get_client(db: Session, name: str) -> ApiClient:
    client = db.scalar(select(ApiClient).where(ApiClient.name == name))
    if client is None:
        raise NotFoundError(f"Sistema '{name}' não encontrado.")
    return client


@router.post("/clients", response_model=ClientCreated, status_code=status.HTTP_201_CREATED)
def create_client(body: ClientIn, db: Session = Depends(get_db)):
    if db.scalar(select(ApiClient).where(ApiClient.name == body.name)):
        raise Conflict(f"Sistema '{body.name}' já cadastrado.")
    key = generate_api_key()
    client = ApiClient(name=body.name, allowed_channels=body.allowed_channels,
                       rate_limit_per_minute=body.rate_limit_per_minute, key_hash=hash_api_key(key))
    db.add(client)
    db.commit()
    return ClientCreated(**ClientOut.model_validate(client).model_dump(), api_key=key)


@router.get("/clients", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db)):
    return list(db.scalars(select(ApiClient).order_by(ApiClient.name)))


@router.patch("/clients/{name}", response_model=ClientOut)
def update_client(name: str, body: ClientUpdate, db: Session = Depends(get_db)):
    client = _get_client(db, name)
    fields = body.model_fields_set  # permite limpar o limite enviando null explicitamente
    if "allowed_channels" in fields and body.allowed_channels is not None:
        client.allowed_channels = body.allowed_channels
    if "rate_limit_per_minute" in fields:
        client.rate_limit_per_minute = body.rate_limit_per_minute
    if "is_active" in fields and body.is_active is not None:
        client.is_active = body.is_active
    db.commit()
    return client


@router.post("/clients/{name}/revoke", response_model=ClientOut)
def revoke_client(name: str, db: Session = Depends(get_db)):
    client = _get_client(db, name)
    client.is_active = False
    db.commit()
    return client


@router.post("/clients/{name}/rotate-key", response_model=ClientCreated)
def rotate_key(name: str, db: Session = Depends(get_db)):
    """Gera uma nova API Key (a anterior deixa de funcionar imediatamente)."""
    client = _get_client(db, name)
    key = generate_api_key()
    client.key_hash = hash_api_key(key)
    db.commit()
    return ClientCreated(**ClientOut.model_validate(client).model_dump(), api_key=key)


# ---------------- Histórico, auditoria e reenvio ----------------
@router.get("/notifications", response_model=list[NotificationOut])
def search_notifications(
    status_: str | None = Query(default=None, alias="status"),
    origin_system: str | None = None,
    channel: str | None = None,
    recipient: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return NotificationRepository(db).search(status_, origin_system, channel, recipient, limit, offset)


@router.get("/notifications/{notification_id}/audit", response_model=list[AuditOut])
def notification_audit(notification_id: str, db: Session = Depends(get_db)):
    repo = NotificationRepository(db)
    if repo.find_by_id(notification_id) is None:
        raise NotFoundError("Notificação não encontrada.")
    return repo.audit_trail(notification_id)


@router.post("/notifications/{notification_id}/retry", response_model=NotificationOut)
def retry_notification(notification_id: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    n = NotificationService(db).requeue_failed(notification_id)
    dispatch(n.id, n.priority, background)
    return n


# ---------------- Métricas e manutenção ----------------
@router.get("/stats")
def stats(hours: int = Query(default=24, ge=1, le=720), db: Session = Depends(get_db)):
    return StatsService(db).summary(hours)


@router.post("/maintenance/purge")
def purge(db: Session = Depends(get_db)):
    days = get_settings().data_retention_days
    if days <= 0:
        raise ValidationFailed("Retenção desativada (defina DATA_RETENTION_DAYS > 0).")
    return {"retention_days": days, "anonymized": retention_service.purge(db, days)}
