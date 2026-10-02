from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["dashboard"])
_PAGE = Path(__file__).resolve().parents[2] / "static" / "dashboard.html"


@router.get("/admin/dashboard", include_in_schema=False)
def dashboard():
    # A página é estática; todos os dados vêm de /api/v1/admin/* e exigem a admin key.
    return FileResponse(_PAGE, media_type="text/html", headers={"Cache-Control": "no-store"})
