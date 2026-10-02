import httpx

from app.core.config import Settings
from app.providers.base import BaseProvider, Message, ProviderError, classify_http_status


class SmsProvider(BaseProvider):
    """SMS via Twilio REST API."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from):
            raise ProviderError("SMS não configurado (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM).")
        self.s = settings
        self.http = client or httpx.Client(timeout=20)

    def send_message(self, message: Message) -> str | None:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.s.twilio_account_sid}/Messages.json"
        try:
            resp = self.http.post(
                url,
                data={"To": message.to, "From": self.s.twilio_from, "Body": message.body},
                auth=(self.s.twilio_account_sid, self.s.twilio_auth_token),
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Falha de rede no SMS ({type(exc).__name__}).", retryable=True) from exc
        if resp.status_code in (200, 201):
            try:
                return resp.json().get("sid")
            except ValueError:
                return None
        raise ProviderError(f"Twilio retornou {resp.status_code}: {resp.text[:300]}",
                            retryable=classify_http_status(resp.status_code))
