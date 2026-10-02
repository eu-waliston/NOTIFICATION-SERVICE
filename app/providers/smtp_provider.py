import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import Settings
from app.providers.base import BaseProvider, Message, ProviderError


class SmtpProvider(BaseProvider):
    def __init__(self, settings: Settings):
        if not settings.smtp_host or not settings.smtp_from:
            raise ProviderError("Configuração SMTP incompleta (SMTP_HOST / SMTP_FROM).")
        self.s = settings

    def send_message(self, message: Message) -> str | None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = message.subject
        msg["From"] = self.s.smtp_from
        msg["To"] = message.to
        msg.attach(MIMEText(message.body, "html", "utf-8"))
        try:
            with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=20) as smtp:
                if self.s.smtp_use_tls:
                    smtp.starttls()
                if self.s.smtp_user:
                    smtp.login(self.s.smtp_user, self.s.smtp_password)
                smtp.send_message(msg)
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused) as exc:
            raise ProviderError(f"SMTP recusou: {exc}") from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise ProviderError(f"Falha SMTP: {exc}", retryable=True) from exc
        return None
