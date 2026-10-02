import json

import httpx
import pytest

from app.core.config import Settings
from app.providers.base import Message, ProviderError
from app.providers.sms_provider import SmsProvider
from app.providers.teams_provider import TeamsProvider
from app.providers.whatsapp_provider import WhatsAppProvider

from .conftest import ADMIN


def http(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------- Teams ----------
def test_teams_sends_adaptive_card():
    seen = {}

    def handler(req):
        seen["url"], seen["json"] = str(req.url), json.loads(req.content)
        return httpx.Response(202)

    p = TeamsProvider(Settings(teams_webhooks='{"ti":"https://hook.example/abc"}'), http(handler))
    p.send_message(Message(to="ti", subject="Alerta", body="Servidor fora"))
    assert seen["url"] == "https://hook.example/abc"
    card = seen["json"]["attachments"][0]["content"]
    assert card["body"][0]["text"] == "Alerta" and card["body"][1]["text"] == "Servidor fora"


def test_teams_unknown_alias_and_secret_not_leaked():
    p = TeamsProvider(Settings(teams_webhooks='{"ti":"https://hook.example/SECRET"}'), http(lambda r: httpx.Response(500)))
    with pytest.raises(ProviderError) as e:
        p.send_message(Message(to="outro", subject="a", body="b"))
    assert not e.value.retryable
    with pytest.raises(ProviderError) as e:
        p.send_message(Message(to="ti", subject="a", body="b"))
    assert e.value.retryable and "SECRET" not in str(e.value)


def test_teams_requires_config():
    with pytest.raises(ProviderError):
        TeamsProvider(Settings(teams_webhooks="{}"))


# ---------- WhatsApp ----------
S_WA = Settings(whatsapp_token="tok", whatsapp_phone_number_id="123", whatsapp_api_version="v20.0")


def test_whatsapp_text():
    seen = {}

    def handler(req):
        seen["url"], seen["auth"], seen["json"] = str(req.url), req.headers["authorization"], json.loads(req.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.1"}]})

    mid = WhatsAppProvider(S_WA, http(handler)).send_message(Message(to="+5511999999999", subject="", body="Olá"))
    assert mid == "wamid.1"
    assert seen["url"] == "https://graph.facebook.com/v20.0/123/messages"
    assert seen["auth"] == "Bearer tok"
    assert seen["json"]["to"] == "5511999999999" and seen["json"]["type"] == "text"


def test_whatsapp_approved_template():
    seen = {}

    def handler(req):
        seen["json"] = json.loads(req.content)
        return httpx.Response(200, json={"messages": [{"id": "x"}]})

    msg = Message(to="+5511999999999", subject="", body="", extra={"template_name": "aviso", "language": "pt_BR", "params": ["João", 42]})
    WhatsAppProvider(S_WA, http(handler)).send_message(msg)
    t = seen["json"]
    assert t["type"] == "template" and t["template"]["name"] == "aviso"
    assert [p["text"] for p in t["template"]["components"][0]["parameters"]] == ["João", "42"]


@pytest.mark.parametrize("status,retry", [(429, True), (500, True), (400, False), (401, False)])
def test_whatsapp_errors(status, retry):
    p = WhatsAppProvider(S_WA, http(lambda r: httpx.Response(status, text="x")))
    with pytest.raises(ProviderError) as e:
        p.send_message(Message(to="+5511999999999", subject="", body="a"))
    assert e.value.retryable is retry


# ---------- SMS ----------
S_SMS = Settings(twilio_account_sid="AC1", twilio_auth_token="tk", twilio_from="+15550001111")


def test_sms_twilio():
    seen = {}

    def handler(req):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], req.content.decode()
        return httpx.Response(201, json={"sid": "SM1"})

    assert SmsProvider(S_SMS, http(handler)).send_message(Message(to="+5511999999999", subject="", body="Oi")) == "SM1"
    assert "/Accounts/AC1/Messages.json" in seen["url"] and seen["auth"].startswith("Basic ")
    assert "To=%2B5511999999999" in seen["body"] and "Body=Oi" in seen["body"]


def test_sms_requires_config():
    with pytest.raises(ProviderError):
        SmsProvider(Settings())


# ---------- fim a fim pela API ----------
@pytest.fixture
def multi(client):
    import uuid
    r = client.post("/api/v1/admin/clients", headers=ADMIN, json={
        "name": f"multi_{uuid.uuid4().hex[:6]}", "allowed_channels": ["email", "teams", "whatsapp", "sms"]})
    for t in [
        {"name": "alerta_teams", "channel": "teams", "subject": "Alerta {{ sistema }}", "html_content": "{{ sistema }} indisponível", "variables": ["sistema"]},
        {"name": "aviso_sms", "channel": "sms", "html_content": "Código {{ codigo }}", "variables": ["codigo"]},
        {"name": "aviso_wa", "channel": "whatsapp", "html_content": "Olá {{ nome }}", "variables": ["nome"],
         "external_template_name": "aviso_aprovado", "language": "pt_BR"},
    ]:
        client.post("/api/v1/admin/templates", headers=ADMIN, json=t)
    return {"X-API-Key": r.json()["api_key"]}


def test_all_channels_end_to_end(client, multi, provider):
    cases = [
        ("teams", "ti-alertas", "alerta_teams", {"sistema": "ERP"}),
        ("sms", "+55 (11) 99999-0000", "aviso_sms", {"codigo": "123"}),
        ("whatsapp", "+5511988887777", "aviso_wa", {"nome": "Ana"}),
    ]
    for ch, rcpt, tpl, data in cases:
        r = client.post("/api/v1/notifications", headers=multi, json={"channel": ch, "recipient": rcpt, "template": tpl, "data": data})
        assert r.status_code == 202, r.text
        assert client.get(f"/api/v1/notifications/{r.json()['id']}", headers=multi).json()["status"] == "SENT"
    teams, sms, wa = provider.sent
    assert teams.to == "ti-alertas" and teams.subject == "Alerta ERP" and teams.body == "ERP indisponível"
    assert sms.to == "+5511999990000" and sms.body == "Código 123"
    assert wa.extra == {"template_name": "aviso_aprovado", "language": "pt_BR", "params": ["Ana"]}


def test_recipient_validation_per_channel(client, multi, provider):
    for ch, bad, tpl, data in [("sms", "12345", "aviso_sms", {"codigo": "1"}), ("teams", "canal com espaço", "alerta_teams", {"sistema": "x"})]:
        r = client.post("/api/v1/notifications", headers=multi, json={"channel": ch, "recipient": bad, "template": tpl, "data": data})
        assert r.status_code == 422


def test_template_channel_mismatch(client, multi, provider):
    r = client.post("/api/v1/notifications", headers=multi, json={
        "channel": "sms", "recipient": "+5511999990000", "template": "resultado_disponivel", "data": {"cliente": "a", "numero": "1"}})
    assert r.status_code == 422 and "canal" in r.json()["message"]


def test_sms_template_not_html_escaped(client, multi, provider):
    r = client.post("/api/v1/notifications", headers=multi, json={
        "channel": "sms", "recipient": "+5511999990000", "template": "aviso_sms", "data": {"codigo": "A&B"}})
    assert r.status_code == 202 and provider.sent[0].body == "Código A&B"
