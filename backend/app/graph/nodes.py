import json
import logging
from typing import Any, Dict, List

from app.llm import call_llm
from app.email_utils import send_email
from app.weather import check_weather
from app.db_ops import (
    lookup_policy, check_coverage_window, find_prior_claims,
    calculate_payout, log_event,
)
from app.services.settings_service import get_effective_config
from app.graph.state import ClaimState

logger = logging.getLogger("fnol.graph")

# ---------------------------------------------------------------------------
# Agent 1 -- Extraction (LLM node: free text -> structured JSON)
# ---------------------------------------------------------------------------
EXTRACTION_SYSTEM_PROMPT = """You are a claims intake parser for an auto insurer.
Read the claimant's free-text email and return ONLY a JSON object with exactly
these keys: policy_number, incident_date (YYYY-MM-DD or null), location,
description, fault_claimed, damage_type, damage_estimate (a plain number in
USD if a repair cost/estimate is mentioned anywhere in the text, e.g. "$45000"
or "45,000 dollars" becomes 45000 -- or null if no figure is mentioned).
No prose, no markdown fences."""


def extraction_agent(state: ClaimState) -> Dict[str, Any]:
    logger.info("[%s] extract: parsing raw email (%d chars)", state["claim_id"], len(state["raw_email_text"]))
    extracted = call_llm(EXTRACTION_SYSTEM_PROMPT, state["raw_email_text"], expect_json=True)
    extracted_estimate = extracted.pop("damage_estimate", None)

    claim = dict(state.get("claim", {}))
    claim.update({k: v for k, v in extracted.items() if v not in (None, "")})

    result: Dict[str, Any] = {"claim": claim}
    # Only fall back to the LLM-extracted figure if the caller (manual form,
    # or a resume with a fresh number) didn't already supply a nonzero one.
    if not state.get("damage_estimate") and extracted_estimate not in (None, ""):
        try:
            result["damage_estimate"] = float(extracted_estimate)
        except (TypeError, ValueError):
            pass

    logger.info("[%s] extract: merged claim fields=%s, damage_estimate=%s",
                state["claim_id"], claim, result.get("damage_estimate", state.get("damage_estimate")))
    log_event(state["claim_id"], "extract", {"extracted": {**extracted, "damage_estimate": extracted_estimate}, "merged_claim": claim})
    return result


# ---------------------------------------------------------------------------
# Completeness gate -- hardcoded, no AI
# ---------------------------------------------------------------------------
def completeness_gate(state: ClaimState) -> Dict[str, Any]:
    required = get_effective_config()["required_claim_fields"]
    missing = [f for f in required if not state["claim"].get(f)]
    logger.info("[%s] completeness_gate: missing_fields=%s", state["claim_id"], missing)
    log_event(state["claim_id"], "completeness_gate", {"missing_fields": missing})
    return {"missing_fields": missing}


def route_after_completeness(state: ClaimState) -> str:
    return "incomplete" if state["missing_fields"] else "complete"


# ---------------------------------------------------------------------------
# Agent 2 -- Follow-up drafter (LLM node, only runs on the incomplete branch)
# ---------------------------------------------------------------------------
FOLLOWUP_SYSTEM_PROMPT = """You are a claims intake assistant. Write a short,
warm, specific email asking the claimant for exactly the missing information
listed. Do not invent facts about their claim. Return plain text starting
with a 'Subject:' line."""


def _tag_subject(claim_id: str, body_with_subject: str) -> str:
    subject_line, sep, rest = body_with_subject.partition("\n\n")
    subject = subject_line.replace("Subject:", "").strip()
    return f"Subject: [{claim_id}] {subject}{sep}{rest}"


def followup_agent(state: ClaimState) -> Dict[str, Any]:
    cfg = get_effective_config()
    max_attempts = cfg["max_followup_attempts"]
    missing = state["missing_fields"]
    attempt = state.get("followup_count", 0) + 1
    logger.info("[%s] followup: attempt %d/%d, missing=%s", state["claim_id"], attempt, max_attempts, missing)

    if attempt > max_attempts:
        logger.info("[%s] followup: max attempts exceeded -> needs_manual_followup", state["claim_id"])
        log_event(state["claim_id"], "followup_maxed_out", {"attempt": attempt})
        return {"followup_count": attempt, "status": "needs_manual_followup", "followup_email": None}

    body = call_llm(
        FOLLOWUP_SYSTEM_PROMPT,
        f"Missing fields: {missing}\nKnown so far: {state['claim']}",
        expect_json=False,
    )
    body = _tag_subject(state["claim_id"], body)
    logger.info("[%s] followup: drafted email to %s", state["claim_id"], state["claimant_email"])
    send_email(state["claimant_email"], body, claim_id=state["claim_id"])
    log_event(state["claim_id"], "followup_sent", {"attempt": attempt, "missing": missing, "body": body})
    return {"followup_email": body, "status": "awaiting_info", "followup_count": attempt}


# ---------------------------------------------------------------------------
# Policy checks node -- hardcoded, no AI
# ---------------------------------------------------------------------------
def policy_checks_node(state: ClaimState) -> Dict[str, Any]:
    claim = state["claim"]
    logger.info("[%s] policy_checks: looking up policy %s", state["claim_id"], claim["policy_number"])
    policy = lookup_policy(claim["policy_number"])
    if policy is None:
        logger.warning("[%s] policy_checks: unknown policy %s -> rejected_unknown_policy", state["claim_id"], claim["policy_number"])
        log_event(state["claim_id"], "policy_checks", {"result": "unknown_policy"})
        return {"policy": None, "status": "rejected_unknown_policy"}

    coverage_check = check_coverage_window(claim["incident_date"], policy)
    prior_claims = find_prior_claims(claim["policy_number"], claim["incident_date"], state["claim_id"])
    payout = calculate_payout(state.get("damage_estimate", 0.0), policy)
    logger.info(
        "[%s] policy_checks: policy_found=%s coverage=%s prior_claims=%s payout=%.2f",
        state["claim_id"], policy["policy_number"], coverage_check,
        [c["claim_id"] for c in prior_claims], payout,
    )
    log_event(state["claim_id"], "policy_checks", {
        "coverage_check": coverage_check,
        "prior_claims": [c["claim_id"] for c in prior_claims],
        "payout": payout,
    })
    return {"policy": policy, "coverage_check": coverage_check, "prior_claims": prior_claims, "payout": payout}


def route_after_policy_checks(state: ClaimState) -> str:
    return "no_policy" if state.get("policy") is None else "ok"


# ---------------------------------------------------------------------------
# Agent 3 -- Weather-consistency agent (tool-calling agent)
# ---------------------------------------------------------------------------
def weather_agent(state: ClaimState) -> Dict[str, Any]:
    claim = state["claim"]
    location = claim.get("location") or state["policy"]["address"]
    logger.info("[%s] weather_agent: checking %s on %s (claimed damage=%s)",
                state["claim_id"], location, claim["incident_date"], claim.get("damage_type"))
    weather_check = check_weather(location, claim["incident_date"], claim.get("damage_type", "unspecified"))
    logger.info("[%s] weather_agent: result=%s", state["claim_id"], weather_check)
    log_event(state["claim_id"], "weather_agent", weather_check)
    return {"weather_check": weather_check}


# ---------------------------------------------------------------------------
# Agent 4 -- Suspicious-language / fraud-risk agent (LLM node)
# ---------------------------------------------------------------------------
RISK_SYSTEM_PROMPT = """You are a claims fraud-language reviewer. Read the
claim description and return ONLY a JSON object:
{"risk_score": <0.0-1.0>, "notes": "<short reason>"}.
Higher score = more suspicious phrasing or internal inconsistency. Do not
accuse anyone of fraud outright -- just flag language patterns worth a human
look."""


def risk_language_agent(state: ClaimState) -> Dict[str, Any]:
    description = state["claim"].get("description", "")
    risk_notes = call_llm(RISK_SYSTEM_PROMPT, f"Claim description:\n{description}", expect_json=True)
    logger.info("[%s] risk_agent: %s", state["claim_id"], risk_notes)
    log_event(state["claim_id"], "risk_agent", risk_notes)
    return {"risk_notes": risk_notes}


# ---------------------------------------------------------------------------
# Decision node -- hardcoded thresholds, combines the specialist outputs
# ---------------------------------------------------------------------------
def decision_node(state: ClaimState) -> Dict[str, Any]:
    cfg = get_effective_config()
    payout = state["payout"]
    weather_check = state["weather_check"]
    risk_notes = state["risk_notes"]
    coverage_check = state["coverage_check"]
    prior_claims = state.get("prior_claims", [])

    reasons: List[str] = []
    escalate = False

    if not coverage_check["in_window"]:
        escalate = True
        reasons.append(coverage_check["reason"])
    if prior_claims:
        escalate = True
        prior_ids = ", ".join(c["claim_id"] for c in prior_claims)
        reasons.append(
            f"Supersedes prior claim(s) {prior_ids} filed for the same policy/incident date; "
            "those have been marked superseded and this is now the active claim for that incident."
        )
    if payout > cfg["auto_approve_payout_limit"]:
        escalate = True
        reasons.append(f"Payout ${payout:,.2f} exceeds auto-approve limit of ${cfg['auto_approve_payout_limit']:,.2f}.")
    if weather_check.get("matches_claim") is False:
        escalate = True
        reasons.append("Claimed damage is inconsistent with historical weather data for that date/location.")
    if risk_notes.get("risk_score", 0) >= cfg["risk_score_escalate_threshold"]:
        escalate = True
        reasons.append(f"Language risk score {risk_notes.get('risk_score')} meets/exceeds threshold {cfg['risk_score_escalate_threshold']}.")

    if not reasons:
        reasons.append("In coverage window; no prior claim on file; payout within limit; weather consistent; language risk low.")

    decision = {"decision": "escalate_to_manager" if escalate else "auto_approve", "reasons": reasons}
    status = decision["decision"]
    logger.info("[%s] decision: %s -- %s", state["claim_id"], status, "; ".join(reasons))
    log_event(state["claim_id"], "decision", decision)
    return {"decision": decision, "status": status}


# ---------------------------------------------------------------------------
# Agent 5 -- Adjudicator / report writer (LLM node)
# ---------------------------------------------------------------------------
REPORT_SYSTEM_PROMPT = """You are writing a regulator-ready claims decision
report. Summarise the claim, every check performed, its data source, and the
final decision with explicit reasons. Be factual and concise -- do not add
checks that weren't performed."""


def adjudicator_agent(state: ClaimState) -> Dict[str, Any]:
    bundle = {k: state[k] for k in (
        "claim_id", "claim", "policy", "coverage_check", "prior_claims",
        "weather_check", "risk_notes", "payout", "decision",
    )}
    report = call_llm(REPORT_SYSTEM_PROMPT, json.dumps(bundle, default=str), expect_json=False)
    logger.info("[%s] adjudicator: report generated", state["claim_id"])
    log_event(state["claim_id"], "adjudicator", {"report": report})
    return {"report": report}
