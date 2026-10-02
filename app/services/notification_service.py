import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import Conflict, Forbidden, NotFoundError, UnsupportedChannel, ValidationFailed
from app.models.notification import Notification, NotificationStatus
from app.models.user import ApiClient
from app.providers import SUPPORTED_CHANNELS, Message, ProviderError, get_provider
from app.repositories.notification_repository import NotificationRepository
from app.repositories.template_repository import TemplateRepository
from app.schemas import NotificationCreate
from app.services.ai_service import AIService
from app.services.audit_service import AuditService
from app.services.email_service import EmailService
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: Session):
        self.repo = NotificationRepository(db)
        self.templates = TemplateService(TemplateRepository(db))
        self.audit = AuditService(db)
        self.db = db

    # ---- entrada (API) ----
    def create(
        self, client: ApiClient, payload: NotificationCreate, actor: str | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[Notification, bool]:
        """Retorna (notificação, criada). `criada=False` quando a Idempotency-Key já existia."""
        if payload.channel not in SUPPORTED_CHANNELS:
            raise UnsupportedChannel(f"Canal não suportado: {payload.channel}")
        if payload.channel not in (client.allowed_channels or []):
            raise Forbidden(f"O sistema '{client.name}' não tem permissão para o canal '{payload.channel}'.")

        if idempotency_key:
            if len(idempotency_key) > 100:
                raise ValidationFailed("Idempotency-Key deve ter no máximo 100 caracteres.")
            existing = self.repo.find_by_idempotency(client.name, idempotency_key)
            if existing:
                return existing, False

        tpl = self.templates.load_template(payload.template)
        if tpl.channel != payload.channel:
            raise ValidationFailed(f"O template '{tpl.name}' é do canal '{tpl.channel}', não '{payload.channel}'.")
        missing = self.templates.missing_variables(tpl, payload.data)
        if missing:
            raise ValidationFailed(f"Variáveis ausentes em 'data': {', '.join(missing)}")
        subject, body = self.templates.render_template(tpl, payload.data, payload.subject)  # valida cedo

        priority = payload.priority
        if priority == "auto":
            priority = AIService().priority_or_heuristic(subject, body)

        notification = Notification(
            origin_system=client.name, channel=payload.channel, recipient=payload.recipient,
            subject=payload.subject, template=payload.template, data=payload.data, priority=priority,
            idempotency_key=idempotency_key, status=NotificationStatus.PROCESSING.value,
        )
        try:
            self.repo.save(notification)
        except IntegrityError:  # corrida na mesma Idempotency-Key
            self.db.rollback()
            existing = self.repo.find_by_idempotency(client.name, idempotency_key or "")
            if existing:
                return existing, False
            raise
        self.audit.record(notification, "CREATED", "ACCEPTED", actor=actor)
        return notification, True

    def get(self, client: ApiClient, notification_id: str) -> Notification:
        n = self.repo.find_by_id(notification_id)
        if n is None or n.origin_system != client.name:
            raise NotFoundError("Notificação não encontrada.")
        return n

    def requeue_failed(self, notification_id: str, actor: str = "admin") -> Notification:
        """Reenvio manual de uma notificação FAILED (o chamador deve despachá-la na fila)."""
        n = self.repo.find_by_id(notification_id)
        if n is None:
            raise NotFoundError("Notificação não encontrada.")
        if n.status != NotificationStatus.FAILED.value:
            raise Conflict("Apenas notificações com status FAILED podem ser reenviadas.")
        if n.anonymized_at:
            raise Conflict("Notificação anonimizada pela política de retenção; não é possível reenviar.")
        n.attempts, n.sent_at = 0, None
        self.repo.update_status(n, NotificationStatus.PROCESSING)
        self.audit.record(n, "MANUAL_RETRY", "QUEUED", actor=actor)
        return n

    # ---- processamento (worker / background) ----
    def process(self, notification_id: str) -> float | None:
        """Executa o envio. Retorna o atraso (s) para nova tentativa, ou None se finalizado."""
        settings = get_settings()
        n = self.repo.find_by_id(notification_id)
        if n is None or n.status in (NotificationStatus.SENT.value, NotificationStatus.FAILED.value):
            return None

        n.attempts += 1
        self.repo.update_status(n, NotificationStatus.PROCESSING)
        try:
            tpl = self.templates.load_template(n.template)
            subject, body = self.templates.render_template(tpl, n.data or {}, n.subject)
            provider = get_provider(n.channel)
            if n.channel == "email":
                EmailService(provider).send_email(n.recipient, subject, body)
            else:
                extra = {}
                if n.channel == "whatsapp" and tpl.external_template_name:
                    extra = {
                        "template_name": tpl.external_template_name,
                        "language": tpl.language,
                        "params": [(n.data or {}).get(v, "") for v in (tpl.variables or [])],
                    }
                provider.send_message(Message(to=n.recipient, subject=subject, body=body, extra=extra))
        except ProviderError as exc:
            if exc.retryable and n.attempts < settings.max_attempts:
                delay = settings.retry_backoff_seconds * (2 ** (n.attempts - 1))
                self.repo.update_status(n, NotificationStatus.PROCESSING, str(exc))
                self.audit.record(n, "SEND", "RETRY", detail=str(exc))
                logger.warning("Notificação %s: nova tentativa em %.0fs (%s)", n.id, delay, exc)
                return delay
            self.repo.update_status(n, NotificationStatus.FAILED, str(exc))
            self.audit.record(n, "SEND", "FAILED", detail=str(exc))
            return None
        except Exception as exc:  # erros não retentáveis (template, configuração...)
            logger.exception("Falha ao processar notificação %s", n.id)
            msg = str(getattr(exc, "message", exc))
            self.repo.update_status(n, NotificationStatus.FAILED, msg)
            self.audit.record(n, "SEND", "FAILED", detail=msg)
            return None

        self.repo.update_status(n, NotificationStatus.SENT)
        self.audit.record(n, "SEND", "SENT")
        return None
