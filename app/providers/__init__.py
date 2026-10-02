from functools import lru_cache

from app.core.channels import SUPPORTED_CHANNELS
from app.core.config import get_settings
from app.core.exceptions import UnsupportedChannel
from app.providers.base import BaseProvider, EmailMessage, Message, ProviderError


def _build_email() -> BaseProvider:
    s = get_settings()
    name = s.email_provider.lower()
    if name == "graph":
        from app.providers.microsoft_graph import MicrosoftGraphProvider
        return MicrosoftGraphProvider(s)
    if name == "smtp":
        from app.providers.smtp_provider import SmtpProvider
        return SmtpProvider(s)
    if name == "console":
        from app.providers.console_provider import ConsoleProvider
        return ConsoleProvider()
    raise ProviderError(f"EMAIL_PROVIDER desconhecido: {name}")


def _build_teams() -> BaseProvider:
    from app.providers.teams_provider import TeamsProvider
    return TeamsProvider(get_settings())


def _build_whatsapp() -> BaseProvider:
    from app.providers.whatsapp_provider import WhatsAppProvider
    return WhatsAppProvider(get_settings())


def _build_sms() -> BaseProvider:
    from app.providers.sms_provider import SmsProvider
    return SmsProvider(get_settings())


_BUILDERS = {"email": _build_email, "teams": _build_teams, "whatsapp": _build_whatsapp, "sms": _build_sms}


@lru_cache
def _cached(channel: str) -> BaseProvider:
    return _BUILDERS[channel]()


def get_provider(channel: str) -> BaseProvider:
    if channel not in _BUILDERS:
        raise UnsupportedChannel(f"Canal não suportado: {channel}")
    return _cached(channel)


__all__ = ["get_provider", "BaseProvider", "EmailMessage", "Message", "ProviderError", "SUPPORTED_CHANNELS"]
