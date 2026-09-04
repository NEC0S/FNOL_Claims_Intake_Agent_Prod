import logging
import re

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_manager_or_admin
from app.database import pg_connection
from app.models import SqlQueryRequest, SqlQueryResponse

router = APIRouter(prefix="/api/sql", tags=["sql"])
logger = logging.getLogger("fnol.routers.sql")

# Only read-only statements are allowed. Anything else is rejected before it
# ever reaches the database.
_ALLOWED_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create|copy|"
    r"vacuum|call|do|execute|merge|comment|lock|reindex)\b",
    re.IGNORECASE,
)
_MULTI_STATEMENT = re.compile(r";.*\S")  # anything non-trivial after a semicolon


@router.post("/query", response_model=SqlQueryResponse)
def run_query(body: SqlQueryRequest, _: dict = Depends(require_manager_or_admin)):
    sql = body.sql.strip().rstrip(";")
    if not sql:
        raise HTTPException(status_code=400, detail="Empty query.")
    if not _ALLOWED_START.match(sql):
        raise HTTPException(status_code=400, detail="Only SELECT / WITH (read-only) queries are allowed.")
    if _FORBIDDEN.search(sql):
        raise HTTPException(status_code=400, detail="Query contains a disallowed keyword. Only read-only SELECT queries are permitted.")
    if _MULTI_STATEMENT.search(sql + ";"):
        raise HTTPException(status_code=400, detail="Only a single statement is allowed.")

    limit = max(1, min(body.limit, 2000))

    try:
        with pg_connection() as conn:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '10s'")
                cur.execute("SET TRANSACTION READ ONLY")
                # Wrap so an arbitrary user query (which may itself contain a
                # LIMIT, ORDER BY, CTEs, etc.) is still capped defensively.
                wrapped = f"SELECT * FROM ({sql}) AS _user_query LIMIT %s"
                cur.execute(wrapped, (limit + 1,))
                columns = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall()
            conn.rollback()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.warning("run_query failed: %r", exc)
        raise HTTPException(status_code=400, detail=f"Query failed: {exc}")

    truncated = len(rows) > limit
    rows = rows[:limit]
    return SqlQueryResponse(
        columns=columns,
        rows=[list(r) for r in rows],
        row_count=len(rows),
        truncated=truncated,
    )


@router.get("/tables")
def list_tables(_: dict = Depends(require_manager_or_admin)):
    sql = """
        select table_name,
               (select count(*) from information_schema.columns c
                where c.table_name = t.table_name and c.table_schema = 'public') as column_count
        from information_schema.tables t
        where table_schema = 'public'
        order by table_name
    """
    try:
        with pg_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
            conn.rollback()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [{"table_name": r[0], "column_count": r[1]} for r in rows]
