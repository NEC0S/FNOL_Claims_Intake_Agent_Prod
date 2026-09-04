from fastapi import APIRouter, Depends

from app.auth import require_any_role
from app.graph.graph_builder import get_graph_mermaid

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/graph/mermaid")
def graph_mermaid(_: dict = Depends(require_any_role)):
    return {"mermaid": get_graph_mermaid()}
