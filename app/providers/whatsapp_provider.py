import httpx

from app.core.config import Settings
from app.providers.base import BaseProvider, Message, ProviderError, classify_http_status


class WhatsAppProvider(BaseProvider):
    """WhatsApp Business Cloud API (Meta).

    Com `extra["template_name"]` envia um template aprovado (permitido a qualquer momento);
    sem ele envia texto livre, que a Meta só entrega dentro da janela de 24h de conversa.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
            raise ProviderError("WhatsApp não configurado (WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID).")
        self.s = settings
        self.http = client or httpx.Client(timeout=20)

    def send_message(self, message: Message) -> str | None:
        payload: dict = {"messaging_product": "whatsapp", "to": message.to.lstrip("+")}
        template_name = message.extra.get("template_name")
        if template_name:
            tpl: dict = {"name": template_name, "language": {"code": message.extra.get("language") or "pt_BR"}}
            params = message.extra.get("params") or []
            if params:
                tpl["components"] = [{"type": "body", "parameters": [{"type": "text", "text": str(p)} for p in params]}]
            payload.update(type="template", template=tpl)
        else:
            payload.update(type="text", text={"body": message.body, "preview_url": False})

        url = f"https://graph.facebook.com/{self.s.whatsapp_api_version}/{self.s.whatsapp_phone_number_id}/messages"
        try:
            resp = self.http.post(url, json=payload, headers={"Authorization": f"Bearer {self.s.whatsapp_token}"})
        except httpx.HTTPError as exc:
            raise ProviderError(f"Falha de rede no WhatsApp ({type(exc).__name__}).", retryable=True) from exc
        if resp.status_code == 200:
            try:
                return resp.json()["messages"][0]["id"]
            except (KeyError, IndexError, ValueError):
                return None
        raise ProviderError(f"WhatsApp retornou {resp.status_code}: {resp.text[:300]}",
                            retryable=classify_http_status(resp.status_code))
