import logging
from collections import Counter
from typing import Dict

from fastapi import APIRouter, Depends

from app.auth import require_any_role
from app.database import supabase
from app.graph.orchestration import manager_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
logger = logging.getLogger("fnol.routers.dashboard")


@router.get("")
def dashboard(_: dict = Depends(require_any_role)):
    return manager_dashboard()


@router.get("/stats")
def stats(_: dict = Depends(require_any_role)):
    res = supabase.table("claims").select("status,payout,damage_type,source,created_at,is_duplicate").execute()
    rows = res.data
    status_counts = Counter(r.get("status") or "unknown" for r in rows)
    damage_type_counts = Counter(r.get("damage_type") or "unknown" for r in rows)
    source_counts = Counter(r.get("source") or "unknown" for r in rows)
    total_payout = sum((r.get("payout") or 0) for r in rows if r.get("status") in ("auto_approve", "manager_approved"))
    duplicates = sum(1 for r in rows if r.get("is_duplicate"))

    return {
        "total_claims": len(rows),
        "status_counts": status_counts,
        "damage_type_counts": damage_type_counts,
        "source_counts": source_counts,
        "total_approved_payout": total_payout,
        "duplicate_claims": duplicates,
    }


@router.get("/review-queue")
def review_queue(_: dict = Depends(require_any_role)):
    res = (
        supabase.table("claims").select("claim_id,status,policy_number,claimant_email,payout,created_at")
        .in_("status", ["awaiting_info", "escalate_to_manager", "needs_manual_followup", "rejected_unknown_policy"])
        .is_("superseded_by", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return res.data
