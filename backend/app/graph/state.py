from typing import Any, Dict, List, Optional, TypedDict


class ClaimState(TypedDict, total=False):
    claim_id: str
    raw_email_text: str
    claimant_email: str
    damage_estimate: float
    source: str
    followup_count: int

    claim: Dict[str, Any]
    missing_fields: List[str]
    followup_email: str

    policy: Optional[Dict[str, Any]]
    coverage_check: Dict[str, Any]
    prior_claims: List[Dict[str, Any]]
    weather_check: Dict[str, Any]
    risk_notes: Dict[str, Any]
    payout: float

    decision: Dict[str, Any]
    report: str
    status: str
