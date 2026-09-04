"""
Bootstrap configuration.

Only the values needed to reach the database and to run the web server are
required at process start. Everything that used to be a hard-required env
var in the original notebook (LLM key, SMTP creds, IMAP creds) is now
*optional* here -- it becomes a fallback. The actual value used at runtime
is resolved by app.services.settings_service, which checks the
`app_settings` table (editable from the Settings page in the UI) first and
falls back to these environment variables if the user hasn't entered
anything in the UI yet.
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class Settings:
    # ---- Required to boot the app -----------------------------------
    SUPABASE_URL: str = _get("SUPABASE_URL")
    SUPABASE_KEY: str = _get("SUPABASE_KEY")  # service_role key
    # Direct Postgres connection string (Supabase Project Settings -> Database
    # -> Connection string -> URI). Needed for the ad-hoc SQL query tool and
    # for a few admin migrations. If absent, the SQL query tool is disabled
    # but the rest of the app still works over the Supabase client.
    DATABASE_URL: str = _get("DATABASE_URL")

    JWT_SECRET: str = _get("JWT_SECRET", "change-me-in-production-please-" + os.urandom(8).hex())
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(_get("JWT_EXPIRE_MINUTES", "720"))

    # Symmetric key used to encrypt sensitive values (SMTP/IMAP passwords,
    # API keys) before they're stored in the app_settings table. Must be a
    # 32-byte urlsafe-base64 key (generate with `Fernet.generate_key()`).
    # If not set, one is generated at process start -- fine for a single
    # instance, but set it explicitly in production so a restart doesn't
    # invalidate previously-saved secrets.
    SETTINGS_ENCRYPTION_KEY: str = _get("SETTINGS_ENCRYPTION_KEY")

    # Bootstrap admin/manager account, created on first startup if the
    # app_users table is empty. Change the password after first login.
    ADMIN_EMAIL: str = _get("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD: str = _get("ADMIN_PASSWORD", "ChangeMe123!")

    # ---- Fallback values (used only if not configured in the Settings UI) --
    LLM_BASE_URL: str = _get("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    LLM_API_KEY: str = _get("LLM_API_KEY")
    LLM_MODEL: str = _get("LLM_MODEL", "gemini-2.0-flash")

    SMTP_HOST: str = _get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(_get("SMTP_PORT", "587"))
    SMTP_USER: str = _get("SMTP_USER")
    SMTP_PASSWORD: str = _get("SMTP_PASSWORD")

    IMAP_HOST: str = _get("IMAP_HOST", "imap.gmail.com")
    IMAP_PORT: int = int(_get("IMAP_PORT", "993"))
    IMAP_USER: str = _get("IMAP_USER")
    IMAP_PASSWORD: str = _get("IMAP_PASSWORD")
    IMAP_MAILBOX: str = _get("IMAP_MAILBOX", "INBOX")

    AUTO_APPROVE_PAYOUT_LIMIT: float = float(_get("AUTO_APPROVE_PAYOUT_LIMIT", "1500.0"))
    RISK_SCORE_ESCALATE_THRESHOLD: float = float(_get("RISK_SCORE_ESCALATE_THRESHOLD", "0.3"))
    MAX_FOLLOWUP_ATTEMPTS: int = int(_get("MAX_FOLLOWUP_ATTEMPTS", "3"))
    POLL_INTERVAL_SECONDS: int = int(_get("POLL_INTERVAL_SECONDS", "60"))
    POLLING_ENABLED_ON_BOOT: bool = _get("POLLING_ENABLED_ON_BOOT", "false").lower() == "true"

    REQUIRED_CLAIM_FIELDS = ["policy_number", "incident_date", "location", "description"]

    CORS_ORIGINS: list = [o.strip() for o in _get("CORS_ORIGINS", "*").split(",") if o.strip()]


settings = Settings()

if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
    raise RuntimeError(
        "Missing SUPABASE_URL / SUPABASE_KEY. These two are the only hard "
        "requirements at boot -- everything else (LLM key, SMTP, IMAP) can "
        "be entered later from the Settings page."
    )
