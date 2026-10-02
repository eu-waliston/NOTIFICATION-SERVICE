from email_validator import EmailNotValidError, validate_email

from app.models.template import Template
from app.providers import BaseProvider, Message
from app.services.template_service import TemplateService


class EmailService:
    def __init__(self, provider: BaseProvider):
        self.provider = provider

    @staticmethod
    def validate_email(address: str) -> bool:
        try:
            validate_email(address, check_deliverability=False)
            return True
        except EmailNotValidError:
            return False

    @staticmethod
    def process_template(template: Template, data: dict, subject: str | None = None) -> tuple[str, str]:
        return TemplateService.render_template(template, data, subject)

    def send_email(self, to: str, subject: str, html: str) -> str | None:
        return self.provider.send_message(Message(to=to, subject=subject, body=html))
