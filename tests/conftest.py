import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ADMIN_API_KEY"] = "admin-test"
os.environ["EMAIL_PROVIDER"] = "console"
os.environ["REDIS_URL"] = ""
os.environ["RETRY_BACKOFF_SECONDS"] = "0"
os.environ["MAX_ATTEMPTS"] = "3"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.base import BaseProvider, ProviderError

ADMIN = {"X-Admin-Key": "admin-test"}


class FakeProvider(BaseProvider):
    def __init__(self):
        self.sent = []
        self.failures: list[ProviderError] = []

    def send_message(self, message):
        if self.failures:
            raise self.failures.pop(0)
        self.sent.append(message)
        return "fake-id"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def provider(monkeypatch):
    p = FakeProvider()
    monkeypatch.setattr("app.services.notification_service.get_provider", lambda channel: p)
    return p


@pytest.fixture
def api_key(client):
    import uuid
    name = f"sys_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/admin/clients", json={"name": name}, headers=ADMIN)
    assert r.status_code == 201
    return {"name": name, "headers": {"X-API-Key": r.json()["api_key"]}}


@pytest.fixture(scope="session", autouse=True)
def seed_template(client):
    client.post("/api/v1/admin/templates", headers=ADMIN, json={
        "name": "resultado_disponivel",
        "subject": "Resultado {{ numero }} disponível",
        "html_content": "<p>Olá, {{ cliente }}! O resultado {{ numero }} está disponível.</p>",
        "variables": ["cliente", "numero"],
    })
