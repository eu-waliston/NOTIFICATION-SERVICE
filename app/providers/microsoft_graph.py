import threading
import time

import httpx

from app.core.config import Settings
from app.providers.base import BaseProvider, Message, ProviderError

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
SEND_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


class MicrosoftGraphProvider(BaseProvider):
    """Envio via Microsoft Graph usando OAuth 2.0 client credentials (permissão Mail.Send)."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        missing = [
            n for n in ("graph_tenant_id", "graph_client_id", "graph_client_secret", "graph_sender")
            if not getattr(settings, n)
        ]
        if missing:
            raise ProviderError(f"Configuração do Graph incompleta: {', '.join(missing).upper()}")
        self.s = settings
        self.http = client or httpx.Client(timeout=20)
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def authenticate(self) -> str:
        try:
            resp = self.http.post(
                TOKEN_URL.format(tenant=self.s.graph_tenant_id),
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.s.graph_client_id,
                    "client_secret": self.s.graph_client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Falha de rede na autenticação: {exc}", retryable=True) from exc
        if resp.status_code != 200:
            raise ProviderError(
                f"Autenticação Graph falhou ({resp.status_code}).",
                retryable=resp.status_code >= 500,
            )
        body = resp.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + int(body.get("expires_in", 3600))
        return self._token

    def refresh_token(self) -> str:
        """Client credentials não possui refresh token: obtém-se um novo access token."""
        with self._lock:
            return self.authenticate()

    def _get_token(self) -> str:
        with self._lock:
            if self._token is None or time.time() > self._expires_at - 60:
                return self.authenticate()
            return self._token

    def _post_mail(self, message: Message, token: str) -> httpx.Response:
        payload = {
            "message": {
                "subject": message.subject,
                "body": {"contentType": "HTML", "content": message.body},
                "toRecipients": [{"emailAddress": {"address": message.to}}],
            },
            "saveToSentItems": False,
        }
        return self.http.post(
            SEND_URL.format(sender=self.s.graph_sender),
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    def send_message(self, message: Message) -> str | None:
        token = self._get_token()
        try:
            resp = self._post_mail(message, token)
            if resp.status_code == 401:
                resp = self._post_mail(message, self.refresh_token())
        except httpx.HTTPError as exc:
            raise ProviderError(f"Falha de rede no envio: {exc}", retryable=True) from exc

        if resp.status_code == 202:
            return resp.headers.get("request-id")
        retryable = resp.status_code in (408, 429) or resp.status_code >= 500
        raise ProviderError(f"Graph retornou {resp.status_code}: {resp.text[:300]}", retryable=retryable)
