import json

import httpx
import pytest

from app.core.config import Settings
from app.core.exceptions import BadGateway, ServiceUnavailable
from app.services.ai_service import AIService, heuristic_priority

from .conftest import ADMIN


def ai(reply: str, status=200, captured=None):
    def handler(req):
        if captured is not None:
            captured.append(json.loads(req.content))
            captured.append(req.headers["x-api-key"])
        return httpx.Response(status, json={"content": [{"type": "text", "text": reply}]})
    return AIService(Settings(anthropic_api_key="k", anthropic_model="m"), httpx.Client(transport=httpx.MockTransport(handler)))


def test_disabled_without_key():
    s = AIService(Settings())
    assert not s.enabled
    with pytest.raises(ServiceUnavailable):
        s.generate_template("aviso de resultado")
    assert s.priority_or_heuristic("Falha crítica", "servidor fora do ar") == "high"


def test_generate_template_derives_variables_from_text():
    cap = []
    reply = 'Claro!\n```json\n{"name":"Aviso Resultado!","description":"d","subject":"Resultado {{ numero }}","html_content":"<p>Olá {{ cliente }}</p>","variables":["inventada"]}\n```'
    out = ai(reply, captured=cap).generate_template("aviso de resultado", "email")
    assert out["name"] == "aviso_resultado_" and out["variables"] == ["cliente", "numero"]
    assert cap[0]["model"] == "m" and cap[1] == "k"


def test_generate_template_bad_output():
    with pytest.raises(BadGateway):
        ai("sem json").generate_template("aviso de resultado")


def test_classify_and_replies_and_analysis():
    assert ai("HIGH").classify_priority("a", "b") == "high"
    assert ai("???").classify_priority("a", "b") == "normal"
    assert ai('{"replies":["a","b","c","d"]}').suggest_replies("oi", count=2) == ["a", "b"]
    assert ai("Causa provável: credenciais expiradas.").analyze_failures({"failed": 3}).startswith("Causa")


def test_ai_failure_falls_back_to_heuristic():
    assert ai("x", status=500).priority_or_heuristic("Newsletter", "novidades do mês") == "low"


def test_heuristics():
    assert heuristic_priority("Olá", "tudo bem") == "normal"
    assert heuristic_priority("URGENTE", "") == "high"


def test_endpoints(client, monkeypatch):
    assert client.get("/api/v1/admin/ai/status", headers=ADMIN).json() == {"enabled": False}
    assert client.post("/api/v1/admin/ai/generate-template", headers=ADMIN, json={"description": "aviso de resultado"}).status_code == 503
    r = client.post("/api/v1/admin/ai/classify-priority", headers=ADMIN, json={"subject": "Incidente", "body": "sistema indisponível"})
    assert r.json() == {"priority": "high", "method": "heuristic"}

    monkeypatch.setattr("app.api.routes.ai_routes.AIService", lambda: ai('{"replies":["Obrigado pelo contato!"]}'))
    r = client.post("/api/v1/admin/ai/suggest-reply", headers=ADMIN, json={"message": "Quando fica pronto?"})
    assert r.json() == {"replies": ["Obrigado pelo contato!"]}
    r = client.get("/api/v1/admin/ai/failure-analysis", headers=ADMIN)
    assert r.status_code == 200 and "alert" in r.json()


def test_auto_priority_on_notification(client, api_key, provider):
    r = client.post("/api/v1/notifications", headers=api_key["headers"], json={
        "channel": "email", "recipient": "cliente@email.com", "template": "resultado_disponivel",
        "data": {"cliente": "A", "numero": "1"}, "subject": "Falha crítica no sistema", "priority": "auto"})
    assert r.status_code == 202
    n = client.get("/api/v1/admin/notifications", headers=ADMIN, params={"origin_system": api_key["name"]}).json()[0]
    assert n["priority"] == "high"
