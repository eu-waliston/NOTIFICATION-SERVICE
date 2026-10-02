from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.queue import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(response: Response, db: Session = Depends(get_db)):
    checks = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    r = get_redis()
    if r is None:
        checks["queue"] = "inline"
    else:
        try:
            r.ping()
            checks["queue"] = "ok"
        except Exception:
            checks["queue"] = "error"
    ok = "error" not in checks.values()
    if not ok:
        response.status_code = 503
    return {"status": "ready" if ok else "degraded", "checks": checks}
