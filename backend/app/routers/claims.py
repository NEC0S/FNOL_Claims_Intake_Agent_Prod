import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user, require_any_role, require_manager_or_admin
from app.database import supabase
from app.db_ops import db_get_claim, get_claim_events, log_event
from app.graph.orchestration import process_claim, resume_claim
from app.models import NewClaimRequest, ResumeClaimRequest, ReviewActionRequest, ClaimUpdateRequest

router = APIRouter(prefix="/api/claims", tags=["claims"])
logger = logging.getLogger("fnol.routers.claims")


@router.get("")
def list_claims(
    status: Optional[str] = Query(None, description="Comma-separated statuses to filter by"),
    search: Optional[str] = Query(None, description="Search claim_id, policy_number, claimant_email"),
    include_superseded: bool = Query(False),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    _: dict = Depends(require_any_role),
):
    q = supabase.table("claims").select("*", count="exact")
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        q = q.in_("status", statuses)
    if not include_superseded:
        q = q.is_("superseded_by", "null")
    if search:
        q = q.or_(
            f"claim_id.ilike.%{search}%,policy_number.ilike.%{search}%,claimant_email.ilike.%{search}%"
        )
    q = q.order("created_at", desc=True).range(offset, offset + limit - 1)
    res = q.execute()
    return {"claims": res.data, "total": res.count}


@router.get("/{claim_id}")
def get_claim(claim_id: str, _: dict = Depends(require_any_role)):
    claim = db_get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    events = get_claim_events(claim_id)
    reviews = supabase.table("claim_reviews").select("*").eq("claim_id", claim_id).order("created_at").execute().data
    emails = supabase.table("email_log").select("*").eq("claim_id", claim_id).order("created_at").execute().data
    return {"claim": claim, "events": events, "reviews": reviews, "emails": emails}


@router.post("")
def create_claim(body: NewClaimRequest, user: dict = Depends(require_any_role)):
    try:
        result = process_claim(
            raw_email_text=body.raw_email_text,
            claimant_email=body.claimant_email,
            damage_estimate=body.damage_estimate,
            claim_id=body.claim_id,
            source=body.source or "manual",
        )
    except Exception as exc:
        logger.exception("create_claim failed")
        raise HTTPException(status_code=500, detail=str(exc))
    log_event(result["claim_id"], "created_via_ui", {"by": user["email"]}, actor=user["email"])
    return result


@router.post("/{claim_id}/resume")
def resume_claim_endpoint(claim_id: str, body: ResumeClaimRequest, user: dict = Depends(require_any_role)):
    try:
        result = resume_claim(claim_id, body.followup_email_text, body.damage_estimate)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("resume_claim failed")
        raise HTTPException(status_code=500, detail=str(exc))
    log_event(claim_id, "resumed_via_ui", {"by": user["email"]}, actor=user["email"])
    return result


@router.post("/{claim_id}/review")
def review_claim(claim_id: str, body: ReviewActionRequest, user: dict = Depends(require_any_role)):
    claim = db_get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    supabase.table("claim_reviews").insert({
        "claim_id": claim_id, "reviewer_email": user["email"],
        "action": body.action, "notes": body.notes,
    }).execute()

    status_map = {
        "approve": "manager_approved",
        "reject": "manager_rejected",
        "request_info": "awaiting_info",
        "escalate": "escalate_to_manager",
    }
    new_status = body.new_status or status_map.get(body.action)
    if new_status:
        supabase.table("claims").update({"status": new_status}).eq("claim_id", claim_id).execute()

    log_event(claim_id, "manual_review", {"action": body.action, "notes": body.notes, "new_status": new_status}, actor=user["email"])
    return {"ok": True, "new_status": new_status}


@router.patch("/{claim_id}")
def update_claim(claim_id: str, body: ClaimUpdateRequest, user: dict = Depends(require_manager_or_admin)):
    claim = db_get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return {"ok": True, "updated": {}}
    supabase.table("claims").update(updates).eq("claim_id", claim_id).execute()
    log_event(claim_id, "manual_edit", updates, actor=user["email"])
    return {"ok": True, "updated": updates}


@router.get("/{claim_id}/events")
def claim_events(claim_id: str, _: dict = Depends(require_any_role)):
    return get_claim_events(claim_id)
