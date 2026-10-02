from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Message:
    """Mensagem genérica de saída (qualquer canal)."""

    to: str
    subject: str
    body: str
    extra: dict = field(default_factory=dict)

    @property
    def html(self) -> str:  # compatibilidade com o canal de email
        return self.body


EmailMessage = Message


class ProviderError(Exception):
    """Erro de provedor. `retryable` indica se vale tentar novamente."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class BaseProvider(ABC):
    @abstractmethod
    def send_message(self, message: Message) -> str | None:
        """Envia a mensagem. Retorna um identificador externo (se houver)."""


def classify_http_status(status: int) -> bool:
    """True se o status HTTP indica falha temporária."""
    return status in (408, 429) or status >= 500
