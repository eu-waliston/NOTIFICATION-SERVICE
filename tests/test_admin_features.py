import uuid
from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.providers.base import ProviderError
from app.services import retention_service

from .conftest import ADMIN

BODY = {"channel": "email", "recipient": "cliente@email.com", "template": "resultado_disponivel",
        "data": {"cliente": "João", "numero": "12345"}}


def test_dashboard_served(client):
    r = client.get("/admin/dashboard")
    assert r.status_code == 200 and "Notification Service" in r.text and "innerHTML" not in r.text


def test_idempotency_key(client, api_key, provider):
    h = {**api_key["headers"], "Idempotency-Key": "pedido-1"}
    a = client.post("/api/v1/notifications", json=BODY, headers=h).json()
    b = client.post("/api/v1/notifications", json=BODY, headers=h).json()
    assert a["id"] == b["id"] and len(provider.sent) == 1


def test_rate_limit(client, provider):
    r = client.post("/api/v1/admin/clients", headers=ADMIN, json={"name": f"lim_{uuid.uuid4().hex[:6]}", "rate_limit_per_minute": 2})
    h = {"X-API-Key": r.json()["api_key"]}
    codes = [client.post("/api/v1/notifications", json=BODY, headers=h).status_code for _ in range(3)]
    assert codes == [202, 202, 429]
    res = client.post("/api/v1/notifications", json=BODY, headers=h)
    assert res.headers["retry-after"] == "60" and res.json()["error"] == "rate_limited"


def test_client_update_and_rotate_key(client, provider):
    name = f"upd_{uuid.uuid4().hex[:6]}"
    created = client.post("/api/v1/admin/clients", headers=ADMIN, json={"name": name}).json()
    old = {"X-API-Key": created["api_key"]}
    r = client.patch(f"/api/v1/admin/clients/{name}", headers=ADMIN, json={"allowed_channels": ["email", "sms"], "rate_limit_per_minute": 5})
    assert r.json()["allowed_channels"] == ["email", "sms"] and r.json()["rate_limit_per_minute"] == 5
    r = client.patch(f"/api/v1/admin/clients/{name}", headers=ADMIN, json={"rate_limit_per_minute": None})
    assert r.json()["rate_limit_per_minute"] is None
    assert client.patch(f"/api/v1/admin/clients/{name}", headers=ADMIN, json={"allowed_channels": ["fax"]}).status_code == 422

    new_key = client.post(f"/api/v1/admin/clients/{name}/rotate-key", headers=ADMIN).json()["api_key"]
    assert client.post("/api/v1/notifications", json=BODY, headers=old).status_code == 401
    assert client.post("/api/v1/notifications", json=BODY, headers={"X-API-Key": new_key}).status_code == 202

    client.patch(f"/api/v1/admin/clients/{name}", headers=ADMIN, json={"is_active": False})
    assert client.post("/api/v1/notifications", json=BODY, headers={"X-API-Key": new_key}).status_code == 401


def test_search_audit_and_manual_retry(client, api_key, provider):
    provider.failures = [ProviderError("recusado", retryable=False)]
    nid = client.post("/api/v1/notifications", json=BODY, headers={**api_key["headers"], "X-On-Behalf-Of": "maria"}).json()["id"]
    found = client.get("/api/v1/admin/notifications", headers=ADMIN, params={"status": "FAILED", "origin_system": api_key["name"]}).json()
    assert [n["id"] for n in found] == [nid]

    audit = client.get(f"/api/v1/admin/notifications/{nid}/audit", headers=ADMIN).json()
    assert [(a["event"], a["result"]) for a in audit] == [("CREATED", "ACCEPTED"), ("SEND", "FAILED")]
    assert audit[0]["actor"] == "maria"

    r = client.post(f"/api/v1/admin/notifications/{nid}/retry", headers=ADMIN)
    assert r.status_code == 200
    assert client.get(f"/api/v1/notifications/{nid}", headers=api_key["headers"]).json()["status"] == "SENT"
    assert client.post(f"/api/v1/admin/notifications/{nid}/retry", headers=ADMIN).status_code == 409


def test_template_validation(client):
    base = {"name": "inv", "html_content": "<p>{{ a }}</p>", "variables": []}
    r = client.post("/api/v1/admin/templates", headers=ADMIN, json=base)
    assert r.status_code == 422 and "a" in r.json()["message"]
    r = client.post("/api/v1/admin/templates", headers=ADMIN, json={**base, "html_content": "{% if %}", "variables": []})
    assert r.status_code == 422
    r = client.post("/api/v1/admin/templates", headers=ADMIN, json={**base, "html_content": "x", "external_template_name": "t"})
    assert r.status_code == 422
    assert client.post("/api/v1/admin/templates", headers=ADMIN, json={**base, "channel": "fax"}).status_code == 422


def test_stats_endpoint(client, api_key, provider):
    client.post("/api/v1/notifications", json=BODY, headers=api_key["headers"])
    s = client.get("/api/v1/admin/stats", headers=ADMIN, params={"hours": 24}).json()
    assert s["total"] >= 1 and s["by_system"][api_key["name"]]["sent"] == 1
    assert s["timeline"] and s["success_rate"] is not None and "alert" in s


def test_failure_alert_logic():
    from app.services.stats_service import StatsService, evaluate_alert
    assert evaluate_alert(sent=2, failed=4, hours=1)["active"] is True
    assert evaluate_alert(sent=2, failed=1, hours=1)["active"] is False      # poucos eventos
    assert evaluate_alert(sent=19, failed=1, hours=1)["active"] is False     # taxa baixa
    assert evaluate_alert(0, 0, 1)["failure_rate"] == 0.0

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        sys_name = f"alert_{uuid.uuid4().hex[:6]}"
        for i in range(6):
            db.add(Notification(origin_system=sys_name, channel="sms", recipient="+5511999990000", template="t",
                                status="FAILED" if i < 4 else "SENT", error_message="Twilio retornou 400", created_at=now))
        db.commit()
        s = StatsService(db).summary(1)
        assert s["by_system"][sys_name]["failed"] == 4
        assert any(e["error"].startswith("Twilio") for e in s["top_errors"])


def test_retention_anonymizes_old_data(client):
    old = datetime.now(timezone.utc) - timedelta(days=100)
    with SessionLocal() as db:
        n = Notification(origin_system="ret", channel="email", recipient="maria@empresa.com", template="t",
                         data={"cpf": "123"}, status="SENT", created_at=old)
        db.add(n); db.commit()
        db.add(AuditLog(notification_id=n.id, origin_system="ret", recipient="maria@empresa.com", event="SEND", result="SENT"))
        db.commit()
        fresh = Notification(origin_system="ret", channel="email", recipient="novo@empresa.com", template="t", data={"a": 1}, status="SENT")
        db.add(fresh); db.commit()

        assert retention_service.purge(db, 30) >= 1
        db.refresh(n); db.refresh(fresh)
        assert n.data == {} and n.recipient == "m***@empresa.com" and n.anonymized_at
        assert fresh.data == {"a": 1} and fresh.recipient == "novo@empresa.com"
        assert db.query(AuditLog).filter_by(notification_id=n.id).one().recipient == "m***@empresa.com"
        assert retention_service.purge(db, 0) == 0


def test_purge_endpoint_disabled_by_default(client):
    assert client.post("/api/v1/admin/maintenance/purge", headers=ADMIN).status_code == 422


def test_mask_recipient():
    assert retention_service.mask_recipient("+5511999990000") == "***0000"
