from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationFailed
from app.core.security import get_current_client
from app.db import get_db
from app.models.user import ApiClient
from app.repositories.template_repository import TemplateRepository
from app.schemas import TemplatePreview
from app.services.template_service import TemplateService

router = APIRouter(prefix="/api/v1/emails", tags=["email"])


@router.post("/preview", response_class=HTMLResponse)
def preview_email(
    payload: TemplatePreview,
    _: ApiClient = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """Renderiza um template com os dados informados, sem enviar nada."""
    svc = TemplateService(TemplateRepository(db))
    tpl = svc.load_template(payload.template)
    missing = svc.missing_variables(tpl, payload.data)
    if missing:
        raise ValidationFailed(f"Variáveis ausentes em 'data': {', '.join(missing)}")
    _, html = svc.render_template(tpl, payload.data)
    return HTMLResponse(html)
