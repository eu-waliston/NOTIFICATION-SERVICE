from app.providers.base import ProviderError

BODY = {
    "channel": "email",
    "recipient": "cliente@email.com",
    "template": "resultado_disponivel",
    "data": {"cliente": "João", "numero": "12345"},
}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 200


def test_requires_api_key(client):
    assert client.post("/api/v1/notifications", json=BODY).status_code == 401
    assert client.post("/api/v1/notifications", json=BODY, headers={"X-API-Key": "x"}).status_code == 401


def test_send_email_end_to_end(client, api_key, provider):
    r = client.post("/api/v1/notifications", json=BODY, headers={**api_key["headers"], "X-On-Behalf-Of": "maria"})
    assert r.status_code == 202
    assert r.json()["status"] == "PROCESSING"
    nid = r.json()["id"]

    s = client.get(f"/api/v1/notifications/{nid}", headers=api_key["headers"]).json()
    assert s["status"] == "SENT" and s["sent_at"] and s["attempts"] == 1
    assert len(provider.sent) == 1
    msg = provider.sent[0]
    assert msg.to == "cliente@email.com"
    assert msg.subject == "Resultado 12345 disponível"
    assert "João" in msg.html


def test_html_is_escaped(client, api_key, provider):
    body = {**BODY, "data": {"cliente": "<script>x</script>", "numero": "1"}}
    client.post("/api/v1/notifications", json=body, headers=api_key["headers"])
    assert "<script>" not in provider.sent[0].html


def test_missing_variable_and_unknown_template(client, api_key, provider):
    r = client.post("/api/v1/notifications", json={**BODY, "data": {"cliente": "A"}}, headers=api_key["headers"])
    assert r.status_code == 422
    r = client.post("/api/v1/notifications", json={**BODY, "template": "nao_existe"}, headers=api_key["headers"])
    assert r.status_code == 404


def test_invalid_recipient_and_channel(client, api_key, provider):
    assert client.post("/api/v1/notifications", json={**BODY, "recipient": "abc"}, headers=api_key["headers"]).status_code == 422
    r = client.post("/api/v1/notifications", json={**BODY, "channel": "telegram", "recipient": "abc"},
                    headers=api_key["headers"])
    assert r.status_code == 400


def test_retry_then_success(client, api_key, provider):
    provider.failures = [ProviderError("timeout", retryable=True)]
    nid = client.post("/api/v1/notifications", json=BODY, headers=api_key["headers"]).json()["id"]
    s = client.get(f"/api/v1/notifications/{nid}", headers=api_key["headers"]).json()
    assert s["status"] == "SENT" and s["attempts"] == 2


def test_permanent_failure(client, api_key, provider):
    provider.failures = [ProviderError("recusado", retryable=False)]
    nid = client.post("/api/v1/notifications", json=BODY, headers=api_key["headers"]).json()["id"]
    s = client.get(f"/api/v1/notifications/{nid}", headers=api_key["headers"]).json()
    assert s["status"] == "FAILED" and "recusado" in s["error_message"] and s["attempts"] == 1


def test_retries_exhausted(client, api_key, provider):
    provider.failures = [ProviderError("down", retryable=True)] * 5
    nid = client.post("/api/v1/notifications", json=BODY, headers=api_key["headers"]).json()["id"]
    s = client.get(f"/api/v1/notifications/{nid}", headers=api_key["headers"]).json()
    assert s["status"] == "FAILED" and s["attempts"] == 3


def test_isolation_between_systems(client, api_key, provider):
    nid = client.post("/api/v1/notifications", json=BODY, headers=api_key["headers"]).json()["id"]
    other = client.post("/api/v1/admin/clients", json={"name": "outro_sistema"}, headers={"X-Admin-Key": "admin-test"})
    h = {"X-API-Key": other.json()["api_key"]} if other.status_code == 201 else None
    if h:
        assert client.get(f"/api/v1/notifications/{nid}", headers=h).status_code == 404


def test_channel_permission(client, provider):
    admin = {"X-Admin-Key": "admin-test"}
    r = client.post("/api/v1/admin/clients", json={"name": "sem_canais", "allowed_channels": []}, headers=admin)
    assert r.status_code in (201, 409)
    if r.status_code == 201:
        res = client.post("/api/v1/notifications", json=BODY, headers={"X-API-Key": r.json()["api_key"]})
        assert res.status_code == 403


def test_admin_protected(client):
    assert client.get("/api/v1/admin/templates").status_code == 401


def test_preview(client, api_key):
    r = client.post("/api/v1/emails/preview", headers=api_key["headers"],
                    json={"template": "resultado_disponivel", "data": {"cliente": "Ana", "numero": "9"}})
    assert r.status_code == 200 and "Ana" in r.text


def test_revoked_key(client):
    admin = {"X-Admin-Key": "admin-test"}
    r = client.post("/api/v1/admin/clients", json={"name": "revogavel"}, headers=admin)
    key = {"X-API-Key": r.json()["api_key"]}
    client.post("/api/v1/admin/clients/revogavel/revoke", headers=admin)
    assert client.post("/api/v1/notifications", json=BODY, headers=key).status_code == 401
