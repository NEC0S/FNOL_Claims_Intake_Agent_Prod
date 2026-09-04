import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.database import supabase

logger = logging.getLogger("fnol.db_ops")


def lookup_policy(policy_number: str) -> Optional[Dict[str, Any]]:
    res = supabase.table("policies").select("*").eq("policy_number", policy_number).limit(1).execute()
    return res.data[0] if res.data else None


def check_coverage_window(incident_date_str: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    incident_dt = datetime.strptime(incident_date_str, "%Y-%m-%d").date()
    start_dt = datetime.strptime(str(policy["start_date"]), "%Y-%m-%d").date()
    end_dt = datetime.strptime(str(policy["end_date"]), "%Y-%m-%d").date()
    in_window = start_dt <= incident_dt <= end_dt
    return {
        "in_window": in_window,
        "reason": (
            f"Incident date {incident_date_str} falls within active coverage "
            f"({policy['start_date']} to {policy['end_date']})."
            if in_window else
            f"Incident date {incident_date_str} is OUTSIDE the coverage window "
            f"({policy['start_date']} to {policy['end_date']})."
        ),
    }


def find_prior_claims(policy_number: str, incident_date_str: str, exclude_claim_id: str) -> List[Dict[str, Any]]:
    res = (
        supabase.table("claims").select("*")
        .eq("policy_number", policy_number)
        .eq("incident_date", incident_date_str)
        .neq("claim_id", exclude_claim_id)
        .is_("superseded_by", "null")
        .execute()
    )
    return res.data


def calculate_payout(damage_estimate: float, policy: Dict[str, Any]) -> float:
    covered = min(damage_estimate, float(policy["coverage_limit"]))
    return max(0.0, covered - float(policy["deductible"]))


def db_upsert_customer(email_addr: str, name: Optional[str]) -> None:
    if not email_addr:
        return
    supabase.table("customers").upsert({"email": email_addr, "name": name}, on_conflict="email").execute()


def db_insert_claim(record: Dict[str, Any]) -> None:
    supabase.table("claims").insert(record).execute()


def db_upsert_claim(record: Dict[str, Any]) -> None:
    supabase.table("claims").upsert(record, on_conflict="claim_id").execute()


def db_get_claim(claim_id: str) -> Optional[Dict[str, Any]]:
    res = supabase.table("claims").select("*").eq("claim_id", claim_id).limit(1).execute()
    return res.data[0] if res.data else None


def db_mark_superseded(old_claim_id: str, new_claim_id: str) -> None:
    supabase.table("claims").update(
        {"status": "superseded", "superseded_by": new_claim_id}
    ).eq("claim_id", old_claim_id).execute()


def log_event(claim_id: str, event_type: str, payload: Any = None, actor: str = "system") -> None:
    try:
        supabase.table("claim_events").insert({
            "claim_id": claim_id, "event_type": event_type, "actor": actor, "payload": payload,
        }).execute()
    except Exception:
        logger.exception("log_event: failed to write claim_event (non-fatal) claim_id=%s type=%s", claim_id, event_type)


def get_claim_events(claim_id: str) -> List[Dict[str, Any]]:
    res = (
        supabase.table("claim_events").select("*")
        .eq("claim_id", claim_id)
        .order("created_at", desc=False)
        .execute()
    )
    return res.data
