from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db import get_db
from app.schemas import AIClassify, AIGenerateTemplate, AISuggestReply
from app.services.ai_service import AIService
from app.services.stats_service import StatsService

router = APIRouter(prefix="/api/v1/admin/ai", tags=["ai"], dependencies=[Depends(require_admin)])


@router.get("/status")
def ai_status():
    return {"enabled": AIService().enabled}


@router.post("/generate-template")
def generate_template(body: AIGenerateTemplate):
    """Sugere um template (não é salvo). Revise e salve em /admin/templates."""
    return AIService().generate_template(body.description, body.channel, body.language)


@router.post("/classify-priority")
def classify_priority(body: AIClassify):
    ai = AIService()
    return {"priority": ai.priority_or_heuristic(body.subject, body.body), "method": "ai" if ai.enabled else "heuristic"}


@router.post("/suggest-reply")
def suggest_reply(body: AISuggestReply):
    return {"replies": AIService().suggest_replies(body.message, body.context, body.count)}


@router.get("/failure-analysis")
def failure_analysis(hours: int = Query(default=24, ge=1, le=720), db: Session = Depends(get_db)):
    """Detecção de falhas: alerta por regra (sempre) + diagnóstico em texto pela IA (se configurada)."""
    summary = StatsService(db).summary(hours)
    ai = AIService()
    analysis = None
    if ai.enabled and summary["failed"]:
        compact = {k: summary[k] for k in ("window_hours", "total", "sent", "failed", "success_rate",
                                           "by_channel", "by_system", "top_errors", "alert")}
        analysis = ai.analyze_failures(compact)
    return {"alert": summary["alert"], "top_errors": summary["top_errors"], "analysis": analysis}
