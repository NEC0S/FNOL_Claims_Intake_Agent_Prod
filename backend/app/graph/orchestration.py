import logging
import uuid
from typing import Any, Dict, List, Optional

from app.database import supabase
from app.db_ops import db_upsert_customer, db_insert_claim, db_upsert_claim, db_get_claim, db_mark_superseded, log_event
from app.graph.graph_builder import get_graph
from app.graph.state import ClaimState

logger = logging.getLogger("fnol.orchestration")


def _build_claim_record(state: Dict[str, Any]) -> Dict[str, Any]:
    claim = state.get("claim", {})
    return {
        "claim_id": state["claim_id"],
        "policy_number": claim.get("policy_number"),
        "claimant_email": state["claimant_email"],
        "incident_date": claim.get("incident_date"),
        "location": claim.get("location"),
        "description": claim.get("description"),
        "fault_claimed": claim.get("fault_claimed"),
        "damage_type": claim.get("damage_type"),
        "damage_estimate": state.get("damage_estimate", 0.0),
        "payout": state.get("payout"),
        "status": state.get("status"),
        "decision": state.get("decision"),
        "coverage_check": state.get("coverage_check"),
        "risk_notes": state.get("risk_notes"),
        "weather_check": state.get("weather_check"),
        "report": state.get("report"),
        "is_duplicate": bool(state.get("prior_claims")),
        "superseded_by": None,
        "source": state.get("source", "manual"),
        "followup_count": state.get("followup_count", 0),
    }


def _persist_result(state: Dict[str, Any], is_resume: bool = False) -> None:
    if state.get("policy"):
        db_upsert_customer(state["claimant_email"], state["policy"].get("holder_name"))

    record = _build_claim_record(state)
    if is_resume:
        db_upsert_claim(record)
    else:
        db_insert_claim(record)

    for prior in state.get("prior_claims", []):
        db_mark_superseded(prior["claim_id"], state["claim_id"])


def process_claim(
    raw_email_text: str,
    claimant_email: str,
    damage_estimate: float = 0.0,
    claim_id: Optional[str] = None,
    source: str = "manual",
) -> Dict[str, Any]:
    claim_id = claim_id or f"CLM-{uuid.uuid4().hex[:8].upper()}"
    logger.info("[%s] process_claim: starting (source=%s, claimant=%s, damage_estimate=%.2f)",
                claim_id, source, claimant_email, damage_estimate)
    log_event(claim_id, "process_claim_started", {"source": source, "claimant_email": claimant_email})
    state: ClaimState = {
        "claim_id": claim_id,
        "raw_email_text": raw_email_text,
        "claimant_email": claimant_email,
        "damage_estimate": damage_estimate,
        "claim": {},
        "status": "new",
        "source": source,
        "followup_count": 0,
    }
    result = get_graph().invoke(state)
    _persist_result(result, is_resume=False)
    logger.info("[%s] process_claim: finished, status=%s", claim_id, result.get("status"))
    return result


def resume_claim(claim_id: str, followup_email_text: str, damage_estimate: Optional[float] = None) -> Dict[str, Any]:
    logger.info("[%s] resume_claim: starting with follow-up text (%d chars)", claim_id, len(followup_email_text))
    prior = db_get_claim(claim_id)
    if prior is None:
        raise ValueError(f"No existing claim found for {claim_id} -- did the first pass finish and persist?")

    state: ClaimState = {
        "claim_id": claim_id,
        "raw_email_text": followup_email_text,
        "claimant_email": prior["claimant_email"],
        "damage_estimate": damage_estimate if damage_estimate is not None else (prior.get("damage_estimate") or 0.0),
        "claim": {
            k: prior[k] for k in
            ["policy_number", "incident_date", "location", "description", "fault_claimed", "damage_type"]
            if prior.get(k)
        },
        "status": "new",
        "source": prior.get("source", "manual"),
        "followup_count": prior.get("followup_count", 0),
    }
    result = get_graph().invoke(state)
    _persist_result(result, is_resume=True)
    logger.info("[%s] resume_claim: finished, status=%s", claim_id, result.get("status"))
    return result


def fetch_claims_by_status(statuses: List[str]) -> List[Dict[str, Any]]:
    res = (
        supabase.table("claims").select("*")
        .in_("status", statuses)
        .is_("superseded_by", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


def manager_dashboard() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "waiting_on_customer": fetch_claims_by_status(["awaiting_info"]),
        "escalated_to_you": fetch_claims_by_status(
            ["escalate_to_manager", "needs_manual_followup", "rejected_unknown_policy"]
        ),
        "auto_approved": fetch_claims_by_status(["auto_approve"]),
    }
