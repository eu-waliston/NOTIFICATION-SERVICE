import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Notification Service"
    database_url: str = "sqlite:///./notifications.db"
    auto_create_tables: bool = True  # em produção: false + `alembic upgrade head`
    redis_url: str | None = None
    admin_api_key: str = ""

    max_attempts: int = 3
    retry_backoff_seconds: float = 30
    rate_limit_per_minute: int = 120  # padrão por sistema; 0 = sem limite
    data_retention_days: int = 0  # 0 = desativado; >0 anonimiza dados antigos

    # Alerta de falhas (detecção automática)
    failure_alert_threshold: float = 0.3
    failure_alert_min_events: int = 5

    # Email: graph | smtp | console
    email_provider: str = "console"
    graph_tenant_id: str = ""
    graph_client_id: str = ""
    graph_client_secret: str = ""
    graph_sender: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # Teams: JSON {"alias": "https://...webhook workflow url..."}
    teams_webhooks: str = "{}"

    # WhatsApp Business (Cloud API)
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_api_version: str = "v20.0"

    # SMS (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from: str = ""

    # IA (opcional)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    @property
    def teams_webhook_map(self) -> dict[str, str]:
        try:
            data = json.loads(self.teams_webhooks or "{}")
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except ValueError:
            return {}


@lru_cache
def get_settings() -> Settings:
    return Settings()
