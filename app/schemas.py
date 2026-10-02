import re
from datetime import datetime
from typing import Any, Literal

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.channels import SUPPORTED_CHANNELS

_PHONE = re.compile(r"\+?[1-9]\d{7,14}")
_ALIAS = re.compile(r"[A-Za-z0-9_\-\.]{1,100}")


def _check_channels(v: list[str]) -> list[str]:
    bad = [c for c in v if c not in SUPPORTED_CHANNELS]
    if bad:
        raise ValueError(f"Canais inválidos: {', '.join(bad)}. Válidos: {', '.join(SUPPORTED_CHANNELS)}")
    return v


class NotificationCreate(BaseModel):
    channel: str = "email"
    recipient: str = Field(description="email, telefone E.164 (whatsapp/sms) ou alias do canal Teams")
    template: str
    data: dict[str, Any] = Field(default_factory=dict)
    subject: str | None = Field(default=None, description="Sobrescreve o assunto do template.")
    priority: Literal["low", "normal", "high", "auto"] = "normal"

    @field_validator("channel")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()

    @model_validator(mode="after")
    def _validate_recipient(self):
        ch = self.channel
        if ch == "email":
            try:
                self.recipient = validate_email(self.recipient, check_deliverability=False).normalized
            except EmailNotValidError as exc:
                raise ValueError(f"recipient inválido: {exc}") from exc
        elif ch in ("whatsapp", "sms"):
            digits = re.sub(r"[\s\-\(\)]", "", self.recipient)
            if not _PHONE.fullmatch(digits):
                raise ValueError("recipient inválido: use telefone no formato internacional (+5511999999999)")
            self.recipient = "+" + digits.lstrip("+")
        elif ch == "teams":
            if not _ALIAS.fullmatch(self.recipient):
                raise ValueError("recipient inválido: alias de canal Teams (letras, números, _ - .)")
        return self


class NotificationCreated(BaseModel):
    id: str
    status: str


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    origin_system: str
    channel: str
    recipient: str
    subject: str | None
    template: str
    priority: str
    status: str
    attempts: int
    created_at: datetime
    sent_at: datetime | None
    error_message: str | None


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notification_id: str
    origin_system: str
    actor: str | None
    recipient: str
    event: str
    result: str
    detail: str | None
    created_at: datetime


class TemplateIn(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9_\-]+$", max_length=100)
    channel: str = "email"
    description: str | None = None
    subject: str | None = None
    html_content: str
    variables: list[str] = Field(default_factory=list)
    external_template_name: str | None = None
    language: str | None = None

    @field_validator("channel")
    @classmethod
    def _channel(cls, v: str) -> str:
        return _check_channels([v])[0]


class TemplateOut(TemplateIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime


class TemplatePreview(BaseModel):
    template: str
    data: dict[str, Any] = Field(default_factory=dict)


class ClientIn(BaseModel):
    name: str = Field(pattern=r"^[A-Za-z0-9_\-\.]+$", max_length=100)
    allowed_channels: list[str] = Field(default_factory=lambda: ["email"])
    rate_limit_per_minute: int | None = Field(default=None, ge=0)

    _v = field_validator("allowed_channels")(lambda cls, v: _check_channels(v))


class ClientUpdate(BaseModel):
    allowed_channels: list[str] | None = None
    rate_limit_per_minute: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    _v = field_validator("allowed_channels")(lambda cls, v: v if v is None else _check_channels(v))


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    allowed_channels: list[str]
    rate_limit_per_minute: int | None
    is_active: bool


class ClientCreated(ClientOut):
    api_key: str = Field(description="Exibida somente nesta resposta.")


# ---- IA ----
class AIGenerateTemplate(BaseModel):
    description: str = Field(min_length=5, max_length=2000)
    channel: str = "email"
    language: str = "pt-BR"


class AISuggestReply(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    context: str | None = Field(default=None, max_length=2000)
    count: int = Field(default=3, ge=1, le=5)


class AIClassify(BaseModel):
    subject: str = ""
    body: str = Field(min_length=1, max_length=4000)
