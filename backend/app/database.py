import logging
from contextlib import contextmanager

from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger("fnol.db")

supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

_pg_pool = None


def _get_pool():
    """Lazily create a small psycopg2 connection pool against the direct
    Postgres URL, only if DATABASE_URL was provided. Used by the read-only
    SQL query tool and by a couple of startup migrations."""
    global _pg_pool
    if _pg_pool is None and settings.DATABASE_URL:
        import psycopg2.pool

        _pg_pool = psycopg2.pool.SimpleConnectionPool(1, 5, dsn=settings.DATABASE_URL)
    return _pg_pool


@contextmanager
def pg_connection():
    pool = _get_pool()
    if pool is None:
        raise RuntimeError(
            "DATABASE_URL is not configured, so direct SQL access is disabled. "
            "Add the Postgres connection string from Supabase → Project Settings "
            "→ Database → Connection string (URI) as DATABASE_URL to enable the "
            "SQL query tool."
        )
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)
