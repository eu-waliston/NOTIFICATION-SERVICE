import logging

from app.providers.base import BaseProvider, Message

logger = logging.getLogger("notification.console")


class ConsoleProvider(BaseProvider):
    """Apenas registra no log. Útil para desenvolvimento local."""

    def send_message(self, message: Message) -> str | None:
        logger.info("EMAIL (console) to=%s subject=%s bytes=%d", message.to, message.subject, len(message.body))
        return "console"
