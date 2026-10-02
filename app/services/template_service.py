from jinja2 import Environment, StrictUndefined, TemplateError, meta
from jinja2.sandbox import SandboxedEnvironment

from app.core.exceptions import NotFoundError, ValidationFailed
from app.models.template import Template
from app.repositories.template_repository import TemplateRepository

# Email: HTML com autoescape (evita injeção via variáveis). Demais canais e assunto: texto puro.
_html_env = SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)
_text_env = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined)


def find_variables(*sources: str | None) -> list[str]:
    """Variáveis usadas nos textos de um template (para conferência)."""
    found: set[str] = set()
    env = Environment()
    for src in sources:
        if src:
            found |= meta.find_undeclared_variables(env.parse(src))
    return sorted(found)


class TemplateService:
    def __init__(self, repo: TemplateRepository):
        self.repo = repo

    def load_template(self, name: str) -> Template:
        tpl = self.repo.get_by_name(name)
        if tpl is None:
            raise NotFoundError(f"Template '{name}' não encontrado.")
        return tpl

    @staticmethod
    def missing_variables(template: Template, data: dict) -> list[str]:
        return [v for v in (template.variables or []) if v not in data]

    @staticmethod
    def render_template(template: Template, data: dict, subject_override: str | None = None) -> tuple[str, str]:
        """Retorna (assunto, corpo final)."""
        body_env = _html_env if template.channel == "email" else _text_env
        try:
            body = body_env.from_string(template.html_content).render(**data)
            raw_subject = subject_override or template.subject or template.name
            subject = _text_env.from_string(raw_subject).render(**data)
        except TemplateError as exc:
            raise ValidationFailed(f"Erro ao renderizar template '{template.name}': {exc}") from exc
        return subject.strip(), body
