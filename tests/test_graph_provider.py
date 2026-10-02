import httpx
import pytest

from app.core.config import Settings
from app.providers.base import EmailMessage, ProviderError
from app.providers.microsoft_graph import MicrosoftGraphProvider

S = Settings(graph_tenant_id="t", graph_client_id="c", graph_client_secret="s", graph_sender="n@x.com")
MSG = EmailMessage(to="a@b.com", subject="Oi", body="<p>oi</p>")


def make(handler):
    return MicrosoftGraphProvider(S, httpx.Client(transport=httpx.MockTransport(handler)))


def test_send_ok_and_token_cached():
    calls = {"token": 0}

    def handler(req):
        if "oauth2" in req.url.path:
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert req.headers["authorization"] == "Bearer tok"
        assert req.url.path.endswith("/users/n@x.com/sendMail")
        return httpx.Response(202, headers={"request-id": "rid"})

    p = make(handler)
    assert p.send_message(MSG) == "rid"
    p.send_message(MSG)
    assert calls["token"] == 1


def test_401_triggers_token_refresh():
    state = {"tokens": 0}

    def handler(req):
        if "oauth2" in req.url.path:
            state["tokens"] += 1
            return httpx.Response(200, json={"access_token": f"tok{state['tokens']}", "expires_in": 3600})
        return httpx.Response(401 if req.headers["authorization"] == "Bearer tok1" else 202)

    make(handler).send_message(MSG)
    assert state["tokens"] == 2


@pytest.mark.parametrize("status,retryable", [(429, True), (503, True), (400, False), (403, False)])
def test_error_classification(status, retryable):
    def handler(req):
        if "oauth2" in req.url.path:
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(status, text="err")

    with pytest.raises(ProviderError) as e:
        make(handler).send_message(MSG)
    assert e.value.retryable is retryable


def test_incomplete_config():
    with pytest.raises(ProviderError):
        MicrosoftGraphProvider(Settings())
