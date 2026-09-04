import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import supabase
from app.services.inbox_service import process_inbox
from app.services.settings_service import get_effective_config

logger = logging.getLogger("fnol.poller")

_scheduler = BackgroundScheduler()
_lock = threading.Lock()
_state = {
    "running": False,
    "last_run_at": None,
    "last_result": None,
    "last_error": None,
    "job_id": "inbox_poll_job",
}


def poll_once() -> dict:
    """A single poll cycle -- fetch unseen mail, run each through the graph,
    persist, log. Never raises: failures are captured so one bad cycle
    doesn't take a scheduled job down."""
    run_row = None
    try:
        run_row = supabase.table("poll_runs").insert({"status": "running"}).execute().data[0]
    except Exception:
        logger.exception("poll_once: failed to write poll_runs start row (non-fatal)")

    started = datetime.now(timezone.utc)
    try:
        results = process_inbox()
        _state["last_run_at"] = started.isoformat()
        _state["last_result"] = f"{len(results)} claim(s) processed"
        _state["last_error"] = None
        if run_row:
            supabase.table("poll_runs").update({
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "claims_processed": len(results),
                "status": "ok",
            }).eq("id", run_row["id"]).execute()
        logger.info("poll_once: %d claim(s) processed", len(results))
        return {"ok": True, "claims_processed": len(results)}
    except Exception as exc:
        logger.exception("poll_once: poll cycle failed")
        _state["last_run_at"] = started.isoformat()
        _state["last_error"] = str(exc)
        if run_row:
            try:
                supabase.table("poll_runs").update({
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "status": "error", "error": str(exc),
                }).eq("id", run_row["id"]).execute()
            except Exception:
                pass
        return {"ok": False, "error": str(exc)}


def start_polling(interval_seconds: Optional[int] = None) -> dict:
    with _lock:
        interval = interval_seconds or get_effective_config()["poll_interval_seconds"]
        if not _scheduler.running:
            _scheduler.start()
        existing = _scheduler.get_job(_state["job_id"])
        if existing:
            _scheduler.reschedule_job(_state["job_id"], trigger="interval", seconds=interval)
        else:
            _scheduler.add_job(poll_once, "interval", seconds=interval, id=_state["job_id"], next_run_time=datetime.now())
        _state["running"] = True
        logger.info("start_polling: polling every %ds", interval)
        return get_status()


def stop_polling() -> dict:
    with _lock:
        job = _scheduler.get_job(_state["job_id"])
        if job:
            _scheduler.remove_job(_state["job_id"])
        _state["running"] = False
        logger.info("stop_polling: polling stopped")
        return get_status()


def get_status() -> dict:
    job = _scheduler.get_job(_state["job_id"]) if _scheduler.running else None
    return {
        "running": _state["running"] and job is not None,
        "next_run_at": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "last_run_at": _state["last_run_at"],
        "last_result": _state["last_result"],
        "last_error": _state["last_error"],
    }
