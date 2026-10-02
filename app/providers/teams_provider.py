import httpx

from app.core.config import Settings
from app.providers.base import BaseProvider, Message, ProviderError, classify_http_status


class TeamsProvider(BaseProvider):
    """Envia Adaptive Cards para canais do Teams via webhook do Workflows.

    O destinatário (`recipient`) é um alias cadastrado em TEAMS_WEBHOOKS; a URL do webhook
    é segredo e nunca aparece em logs ou mensagens de erro.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.hooks = settings.teams_webhook_map
        if not self.hooks:
            raise ProviderError("Teams não configurado (TEAMS_WEBHOOKS).")
        self.http = client or httpx.Client(timeout=20)

    def send_message(self, message: Message) -> str | None:
        url = self.hooks.get(message.to)
        if not url:
            raise ProviderError(f"Canal Teams '{message.to}' não cadastrado em TEAMS_WEBHOOKS.")
        card = {
            "type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4",
            "body": [
                {"type": "TextBlock", "text": message.subject, "weight": "Bolder", "size": "Medium", "wrap": True},
                {"type": "TextBlock", "text": message.body, "wrap": True},
            ],
        }
        payload = {"type": "message", "attachments": [
            {"contentType": "application/vnd.microsoft.card.adaptive", "contentUrl": None, "content": card}
        ]}
        try:
            resp = self.http.post(url, json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Falha de rede no Teams ({type(exc).__name__}).", retryable=True) from exc
        if resp.status_code in (200, 201, 202):
            return None
        raise ProviderError(f"Teams retornou {resp.status_code}.", retryable=classify_http_status(resp.status_code))
