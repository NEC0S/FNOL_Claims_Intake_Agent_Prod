import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.auth import ensure_bootstrap_admin
from app.services import poller_service

from app.routers import auth, claims, dashboard, settings as settings_router, sql, poller, policies, misc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("fnol")

app = FastAPI(
    title="FNOL Claims Intake API",
    description="Multi-agent LangGraph claims intake backend -- manager & checker API, "
                 "settings management, SQL query tool, and IMAP polling control.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": f"Internal error: {exc}"})


app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(dashboard.router)
app.include_router(settings_router.router)
app.include_router(sql.router)
app.include_router(poller.router)
app.include_router(policies.router)
app.include_router(policies.customers_router)
app.include_router(misc.router)


def _apply_schema_if_possible() -> None:
    if not settings.DATABASE_URL:
        logger.info("startup: DATABASE_URL not set -- skipping automatic schema apply. "
                     "Run backend/app/schema.sql manually in the Supabase SQL editor.")
        return
    try:
        import psycopg2
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r") as f:
            schema_sql = f.read()
        conn = psycopg2.connect(settings.DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
            conn.commit()
            logger.info("startup: schema.sql applied successfully.")
        finally:
            conn.close()
    except Exception:
        logger.exception("startup: automatic schema apply failed (non-fatal) -- "
                          "run backend/app/schema.sql manually if tables are missing.")


@app.on_event("startup")
def on_startup():
    logger.info("startup: applying schema (if DATABASE_URL is set)...")
    _apply_schema_if_possible()
    logger.info("startup: ensuring bootstrap admin account exists...")
    try:
        ensure_bootstrap_admin()
    except Exception:
        logger.exception("startup: ensure_bootstrap_admin failed -- app_users table may be missing. "
                          "Run backend/app/schema.sql in the Supabase SQL editor.")
    if settings.POLLING_ENABLED_ON_BOOT:
        logger.info("startup: POLLING_ENABLED_ON_BOOT=true -- starting IMAP poller.")
        try:
            poller_service.start_polling()
        except Exception:
            logger.exception("startup: failed to auto-start poller (non-fatal)")


@app.get("/")
def root():
    return {"service": "fnol-claims-api", "status": "ok", "docs": "/docs"}
