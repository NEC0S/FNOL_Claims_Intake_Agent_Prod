"""
Effective-config resolver.

Precedence for every runtime-configurable value: value saved in the
`app_settings` table (via the Settings page in the UI) > value in the
process environment (.env / host env vars) > hardcoded default.

Secrets (API keys, SMTP/IMAP passwords) are encrypted at rest in
`app_settings` with a Fernet key (SETTINGS_ENCRYPTION_KEY).
"""
import base64
import hashlib
import logging
from functools import lru_cache
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings as env_settings
from app.database import supabase

logger = logging.getLogger("fnol.settings")

SECRET_KEYS = {
    "llm_api_key", "smtp_password", "imap_password", "google_api_key",
}

# Keys a manager can configure from the UI, grouped by section, with their
# env fallback attribute name on `env_settings` and a type caster.
CONFIGURABLE_KEYS = {
    # LLM / Google Generative AI
    "llm_base_url": ("LLM_BASE_URL", str),
    "llm_api_key": ("LLM_API_KEY", str),
    "llm_model": ("LLM_MODEL", str),
    "google_api_key": ("LLM_API_KEY", str),  # alias: if set, used as the LLM key
    # SMTP (outbound)
    "smtp_host": ("SMTP_HOST", str),
    "smtp_port": ("SMTP_PORT", int),
    "smtp_user": ("SMTP_USER", str),
    "smtp_password": ("SMTP_PASSWORD", str),
    "smtp_use_tls": ("SMTP_USE_TLS", bool),
    # IMAP (inbound)
    "imap_host": ("IMAP_HOST", str),
    "imap_port": ("IMAP_PORT", int),
    "imap_user": ("IMAP_USER", str),
    "imap_password": ("IMAP_PASSWORD", str),
    "imap_mailbox": ("IMAP_MAILBOX", str),
    # Business thresholds
    "auto_approve_payout_limit": ("AUTO_APPROVE_PAYOUT_LIMIT", float),
    "risk_score_escalate_threshold": ("RISK_SCORE_ESCALATE_THRESHOLD", float),
    "max_followup_attempts": ("MAX_FOLLOWUP_ATTEMPTS", int),
    "poll_interval_seconds": ("POLL_INTERVAL_SECONDS", int),
}


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = env_settings.SETTINGS_ENCRYPTION_KEY
    if key:
        # Accept either a raw passphrase or a real Fernet key.
        try:
            return Fernet(key.encode())
        except Exception:
            digest = hashlib.sha256(key.encode()).digest()
            return Fernet(base64.urlsafe_b64encode(digest))
    generated = Fernet.generate_key()
    logger.warning(
        "SETTINGS_ENCRYPTION_KEY not set -- generated an ephemeral key for "
        "this process. Saved secrets will need to be re-entered after a "
        "restart. Set SETTINGS_ENCRYPTION_KEY in production."
    )
    return Fernet(generated)


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        logger.error("settings_service: failed to decrypt a stored secret (key rotated?)")
        return ""


def _db_get_all() -> dict:
    res = supabase.table("app_settings").select("*").execute()
    out = {}
    for row in res.data:
        val = row["value"]
        if row["key"] in SECRET_KEYS and isinstance(val, dict) and val.get("__enc__"):
            val = _decrypt(val["__enc__"])
        elif isinstance(val, dict) and "__plain__" in val:
            val = val["__plain__"]
        out[row["key"]] = val
    return out


def get_effective_config() -> dict:
    """Returns every configurable key resolved DB-first, env-fallback."""
    db_values = _db_get_all()
    resolved = {}
    for key, (env_attr, caster) in CONFIGURABLE_KEYS.items():
        if key in db_values and db_values[key] not in (None, ""):
            raw = db_values[key]
        else:
            raw = getattr(env_settings, env_attr, None)
            if raw is None and env_attr == "SMTP_USE_TLS":
                raw = True
        try:
            resolved[key] = caster(raw) if raw is not None and raw != "" else raw
        except (ValueError, TypeError):
            resolved[key] = raw
    # google_api_key, if explicitly set by the user, wins over llm_api_key
    if db_values.get("google_api_key"):
        resolved["llm_api_key"] = db_values["google_api_key"]
    resolved["required_claim_fields"] = env_settings.REQUIRED_CLAIM_FIELDS
    return resolved


def get_setting(key: str) -> Any:
    return get_effective_config().get(key)


def save_settings(values: dict, updated_by: str = "system") -> None:
    rows = []
    for key, value in values.items():
        if value is None:
            continue
        if key in SECRET_KEYS and value:
            stored = {"__enc__": _encrypt(str(value))}
        else:
            stored = {"__plain__": value}
        rows.append({"key": key, "value": stored, "updated_by": updated_by})
    if rows:
        supabase.table("app_settings").upsert(rows, on_conflict="key").execute()


def get_masked_settings() -> dict:
    """Same as get_effective_config but with secrets redacted, for display
    in the Settings UI (shows whether a value is set, not the value)."""
    cfg = get_effective_config()
    masked = dict(cfg)
    for key in ("llm_api_key", "smtp_password", "imap_password", "google_api_key"):
        if masked.get(key):
            masked[key] = "•" * 8 + str(masked[key])[-4:] if len(str(masked[key])) > 4 else "••••••••"
        else:
            masked[key] = None
    # also report whether it came from env-only (no DB override yet)
    db_values = _db_get_all()
    masked["_source"] = {
        k: ("ui" if k in db_values and db_values[k] not in (None, "") else "env_fallback")
        for k in CONFIGURABLE_KEYS
    }
    return masked
