import hashlib
import hmac
import secrets

from fastapi import Depends, Header
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import Forbidden, Unauthorized
from app.db import get_db
from app.models.user import ApiClient

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def generate_api_key() -> str:
    return "ns_" + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_current_client(
    api_key: str | None = Depends(_api_key_header),
    db: Session = Depends(get_db),
) -> ApiClient:
    """Autentica o sistema chamador pela API Key interna (guardada apenas como hash)."""
    if not api_key:
        raise Unauthorized("API Key ausente (header X-API-Key).")
    client = db.scalar(select(ApiClient).where(ApiClient.key_hash == hash_api_key(api_key)))
    if client is None or not client.is_active:
        raise Unauthorized("API Key inválida ou desativada.")
    return client


def require_admin(admin_key: str | None = Depends(_admin_key_header)) -> None:
    expected = get_settings().admin_api_key
    if not expected:
        raise Forbidden("Rotas administrativas desabilitadas (ADMIN_API_KEY não configurada).")
    if not admin_key or not hmac.compare_digest(admin_key, expected):
        raise Unauthorized("Admin key inválida.")


def get_on_behalf_of(x_on_behalf_of: str | None = Header(default=None)) -> str | None:
    """Usuário final responsável pela ação, informado pelo sistema de origem (auditoria)."""
    return x_on_behalf_of
