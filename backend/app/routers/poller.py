import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_manager_or_admin, require_any_role
from app.database import supabase
from app.services import poller_service

router = APIRouter(prefix="/api/poller", tags=["poller"])
logger = logging.getLogger("fnol.routers.poller")


@router.get("/status")
def status(_: dict = Depends(require_any_role)):
    return poller_service.get_status()


@router.post("/start")
def start(interval_seconds: Optional[int] = None, _: dict = Depends(require_manager_or_admin)):
    return poller_service.start_polling(interval_seconds)


@router.post("/stop")
def stop(_: dict = Depends(require_manager_or_admin)):
    return poller_service.stop_polling()


@router.post("/poll-now")
def poll_now(_: dict = Depends(require_any_role)):
    result = poller_service.poll_once()
    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=result.get("error", "Poll failed"))
    return result


@router.get("/history")
def history(limit: int = 25, _: dict = Depends(require_any_role)):
    res = (
        supabase.table("poll_runs").select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data
