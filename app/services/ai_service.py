"""Recursos de IA (opcionais) usando a API da Anthropic.

Todos os resultados são *sugestões*: nada é salvo ou enviado automaticamente.
Sem ANTHROPIC_API_KEY o serviço fica desabilitado (a classificação de prioridade cai em heurística).
"""
import json
import re

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import BadGateway, ServiceUnavailable
from app.services.template_service import find_variables

API_URL = "https://api.anthropic.com/v1/messages"

_URGENT = ("urgente", "urgência", "crítico", "critico", "emergência", "emergencia", "falha", "erro",
           "alerta", "incidente", "indisponível", "indisponivel", "imediat", "segurança", "seguranca", "urgent",
           "critical", "outage")
_LOW = ("newsletter", "promoção", "promocao", "novidades", "lembrete opcional", "informativo")


def heuristic_priority(subject: str, body: str) -> str:
    text = f"{subject} {body}".lower()
    if any(k in text for k in _URGENT):
        return "high"
    if any(k in text for k in _LOW):
        return "low"
    return "normal"


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise BadGateway("Resposta da IA sem JSON válido.")
    try:
        return json.loads(text[start : end + 1])
    except ValueError as exc:
        raise BadGateway("Resposta da IA com JSON inválido.") from exc


class AIService:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.s = settings or get_settings()
        self.http = client or httpx.Client(timeout=30)

    @property
    def enabled(self) -> bool:
        return bool(self.s.anthropic_api_key)

    def _complete(self, system: str, user: str, max_tokens: int = 1200) -> str:
        if not self.enabled:
            raise ServiceUnavailable("IA não configurada (defina ANTHROPIC_API_KEY).")
        try:
            resp = self.http.post(
                API_URL,
                headers={"x-api-key": self.s.anthropic_api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.s.anthropic_model, "max_tokens": max_tokens, "system": system,
                      "messages": [{"role": "user", "content": user}]},
            )
        except httpx.HTTPError as exc:
            raise BadGateway(f"Falha de rede ao chamar a IA ({type(exc).__name__}).") from exc
        if resp.status_code != 200:
            raise BadGateway(f"IA retornou {resp.status_code}.")
        blocks = resp.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()

    # ---- geração automática de mensagens ----
    def generate_template(self, description: str, channel: str = "email", language: str = "pt-BR") -> dict:
        fmt = ("HTML simples e seguro (sem scripts, sem CSS externo, estilos inline)" if channel == "email"
               else "texto puro, curto e direto")
        system = (
            "Você cria templates de notificações corporativas. Use sintaxe Jinja2 para variáveis ({{ variavel }}), "
            "com nomes em snake_case sem acentos. Responda SOMENTE com um objeto JSON com as chaves: "
            '"name" (snake_case), "description", "subject", "html_content". '
            f"Idioma: {language}. Formato do corpo: {fmt}. Não inclua variáveis além das necessárias."
        )
        data = _extract_json(self._complete(system, f"Canal: {channel}\nPedido: {description}"))
        name = re.sub(r"[^a-z0-9_\-]", "_", str(data.get("name", "novo_template")).lower())[:100] or "novo_template"
        subject = str(data.get("subject") or "")
        content = str(data.get("html_content") or "")
        if not content:
            raise BadGateway("A IA não retornou o conteúdo do template.")
        return {
            "name": name,
            "channel": channel,
            "description": str(data.get("description") or "")[:500],
            "subject": subject,
            "html_content": content,
            "variables": find_variables(content, subject),  # derivadas do texto, não do modelo
        }

    # ---- classificação de prioridade ----
    def classify_priority(self, subject: str, body: str) -> str:
        system = ("Classifique a prioridade de uma notificação corporativa. Responda SOMENTE com uma palavra: "
                  "high (exige ação imediata, incidente, segurança), normal ou low (informativo/promocional).")
        out = self._complete(system, f"Assunto: {subject}\n\n{body[:1500]}", max_tokens=10).lower()
        for p in ("high", "normal", "low"):
            if p in out:
                return p
        return "normal"

    def priority_or_heuristic(self, subject: str, body: str) -> str:
        """Usa IA se disponível; em qualquer falha cai na heurística (nunca bloqueia o envio)."""
        if self.enabled:
            try:
                return self.classify_priority(subject, body)
            except Exception:
                pass
        return heuristic_priority(subject, body)

    # ---- sugestão de respostas ----
    def suggest_replies(self, message: str, context: str | None = None, count: int = 3) -> list[str]:
        system = (f"Você sugere respostas curtas, cordiais e profissionais, em português, para mensagens recebidas "
                  f"de clientes. Responda SOMENTE com um objeto JSON: {{\"replies\": [{count} strings]}}. "
                  "Não invente fatos, prazos ou valores que não estejam no contexto.")
        user = f"Contexto: {context or '(nenhum)'}\n\nMensagem recebida:\n{message}"
        replies = _extract_json(self._complete(system, user)).get("replies", [])
        return [str(r) for r in replies][:count]

    # ---- análise de falhas ----
    def analyze_failures(self, summary: dict) -> str:
        system = ("Você é um engenheiro de confiabilidade. Com base nas estatísticas de um serviço de notificações, "
                  "explique em até 6 linhas, em português, as prováveis causas das falhas e as ações recomendadas. "
                  "Seja específico e não invente dados.")
        return self._complete(system, json.dumps(summary, ensure_ascii=False, default=str), max_tokens=600)
