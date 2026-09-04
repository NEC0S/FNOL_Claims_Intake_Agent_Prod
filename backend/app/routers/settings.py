import logging

from fastapi import APIRouter, Depends

from app.auth import require_manager_or_admin, require_any_role
from app.models import SettingsUpdateRequest
from app.services.settings_service import get_masked_settings, save_settings
from app.email_utils import test_smtp_connection, test_imap_connection
from app.llm import test_llm_connection

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger("fnol.routers.settings")


@router.get("")
def get_settings(_: dict = Depends(require_any_role)):
    return get_masked_settings()


@router.put("")
def update_settings(body: SettingsUpdateRequest, user: dict = Depends(require_manager_or_admin)):
    save_settings(body.values, updated_by=user["email"])
    return {"ok": True, "settings": get_masked_settings()}


@router.post("/test/smtp")
def test_smtp(_: dict = Depends(require_manager_or_admin)):
    return test_smtp_connection()


@router.post("/test/imap")
def test_imap(_: dict = Depends(require_manager_or_admin)):
    return test_imap_connection()


@router.post("/test/llm")
def test_llm(_: dict = Depends(require_manager_or_admin)):
    return test_llm_connection()
