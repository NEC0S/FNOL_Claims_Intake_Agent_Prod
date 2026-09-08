"""
ClaimPilot — Evaluation Harness
---------------------------------
Runs the labeled synthetic test set (see generate_synthetic_claims.py)
through your deployed ClaimPilot pipeline and reports the metrics for:

    "Evaluated on 100 test claims, achieving X% structured-field
     extraction accuracy and Y% decision accuracy."

WIRE-UP REQUIRED before running — see the two TODO blocks below:
  1. call_claimpilot()   — how to submit a claim and get back a result
  2. RESPONSE FIELD MAP  — what your API response actually calls things

Usage:
    python eval_harness.py --testset claims_testset.json --out ./eval_out
"""

import json
import time
import argparse
import statistics
from pathlib import Path
from typing import Any, Optional

import requests
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
API_BASE_URL = "http://localhost:8000"          # TODO: or your Render URL
CLAIM_ENDPOINT = f"{API_BASE_URL}/api/claims"   # POST /api/claims -> create_claim
# GUESS — confirm the real path/shape against your login route once shared.
# Common FastAPI pattern: POST {email, password} -> {"access_token": "..."}.
LOGIN_ENDPOINT = f"{API_BASE_URL}/api/auth/login"

import os


def _fetch_auth_token() -> Optional[str]:
    """
    Prefer an explicitly-set token (CLAIMPILOT_AUTH_TOKEN); otherwise try to
    log in with ADMIN_EMAIL/ADMIN_PASSWORD from the environment. This is a
    best-effort convenience — if your login route/response shape differs,
    set CLAIMPILOT_AUTH_TOKEN directly instead and skip this path.
    """
    token = os.environ.get("CLAIMPILOT_AUTH_TOKEN")
    if token:
        return token

    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not (email and password):
        return None

    try:
        resp = requests.post(
            LOGIN_ENDPOINT,
            data={"username": email, "password": password},  # OAuth2PasswordRequestForm: form-encoded, field is "username"
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("access_token") or data.get("token")
    except Exception as e:
        print(f"[auth] Could not auto-login at {LOGIN_ENDPOINT}: {e}")
        print("[auth] Set CLAIMPILOT_AUTH_TOKEN manually instead, or confirm the login route.")
        return None


AUTH_TOKEN: Optional[str] = _fetch_auth_token()

# Update to match whatever model your agents run on
PRICE_PER_1K_INPUT_TOKENS = 0.00015
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006

FUZZY_MATCH_THRESHOLD = 85     # 0-100, for free-text field comparison
NUMERIC_TOLERANCE_PCT = 0.02   # dollar amounts within 2% count as a match


# ---------------------------------------------------------------------------
# 1) WIRE-UP: submit a claim, return normalized result + timing
# ---------------------------------------------------------------------------
def call_claimpilot(email_text: str, claimant_email: str = "eval-harness@example.com") -> dict:
    """
    Submits one claim email to ClaimPilot and returns a normalized dict:

        {
          "extracted_fields": {...},      # from your extraction agent
          "decision": "approve" | "deny" | "investigate",
          "escalated": bool,
          "token_usage": {"input": int, "output": int} | None,
          "latency_ms": float,
          "raw_response": {...},
        }

    TODO: adjust the request payload and the field names pulled out of the
    JSON response below to match your actual FastAPI endpoint contract.
    """
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

    # NewClaimRequest -> process_claim(raw_email_text=..., claimant_email=..., ...)
    # claimant_email is a placeholder here; swap in claim["ground_truth"] data
    # in run_eval() below if NewClaimRequest requires a real address per claim.
    payload = {"raw_email_text": email_text, "claimant_email": claimant_email}

    start = time.perf_counter()
    resp = requests.post(CLAIM_ENDPOINT, json=payload, headers=headers, timeout=120)
    latency_ms = (time.perf_counter() - start) * 1000
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # FastAPI puts the actually-useful info (which field, why) in the
        # response body, not the status line requests shows by default.
        raise requests.HTTPError(f"{e} | response body: {resp.text}", response=resp) from None
    data = resp.json()

    # ---- RESPONSE FIELD MAP (edit to match your schema) ----
    extracted_fields = data.get("extracted_fields", {})
    decision = data.get("decision", {}).get("outcome") if isinstance(data.get("decision"), dict) else data.get("decision")
    escalated = data.get("escalated", data.get("requires_human_review", False))
    token_usage = data.get("token_usage")  # e.g. {"input": 1200, "output": 340}

    return {
        "extracted_fields": extracted_fields,
        "decision": decision,
        "escalated": bool(escalated),
        "token_usage": token_usage,
        "latency_ms": latency_ms,
        "raw_response": data,
    }


# ---------------------------------------------------------------------------
# Field-level scoring
# ---------------------------------------------------------------------------
def values_match(gt_value: Any, pred_value: Any) -> bool:
    if gt_value is None:
        # Field intentionally omitted from the source — a correct system
        # should return None/empty here, not hallucinate a value.
        return pred_value in (None, "", "null", "N/A")
    if pred_value is None:
        return False

    # Numeric fields (dollar amounts, etc.)
    if isinstance(gt_value, (int, float)):
        try:
            pred_num = float(str(pred_value).replace("$", "").replace(",", ""))
            return abs(pred_num - gt_value) <= max(1.0, gt_value * NUMERIC_TOLERANCE_PCT)
        except (ValueError, TypeError):
            return False

    # String / date / free-text fields
    gt_str, pred_str = str(gt_value).strip().lower(), str(pred_value).strip().lower()
    if gt_str == pred_str:
        return True
    return fuzz.ratio(gt_str, pred_str) >= FUZZY_MATCH_THRESHOLD


def score_extraction(ground_truth: dict, predicted: dict) -> dict:
    results = {}
    for field, gt_value in ground_truth.items():
        pred_value = predicted.get(field)
        results[field] = values_match(gt_value, pred_value)
    return results


def check_hallucination(predicted: dict, ground_truth: dict, source_text: str) -> list[str]:
    """
    Flags predicted field values that are (a) non-null, (b) NOT a correct
    match to ground truth, AND (c) not findable anywhere in the source
    email text. That combination is a strong signal of a fabricated value
    rather than a reasonable extraction miss.
    """
    hallucinated = []
    source_lower = source_text.lower()
    for field, pred_value in predicted.items():
        if pred_value in (None, "", "N/A"):
            continue
        gt_value = ground_truth.get(field)
        if values_match(gt_value, pred_value):
            continue
        if str(pred_value).lower() not in source_lower and fuzz.partial_ratio(str(pred_value).lower(), source_lower) < 60:
            hallucinated.append(field)
    return hallucinated


# ---------------------------------------------------------------------------
# Main eval loop
# ---------------------------------------------------------------------------
def run_eval(testset: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    per_claim_rows = []
    all_field_results: list[bool] = []
    decision_correct = 0
    claims_with_hallucination = 0
    latencies = []
    costs = []
    escalation_predicted = 0
    escalation_expected = 0

    for i, claim in enumerate(testset, 1):
        print(f"[{i}/{len(testset)}] {claim['id']} ({claim['category']})...", end=" ")
        try:
            result = call_claimpilot(claim["email_text"])
        except Exception as e:
            print(f"FAILED: {e}")
            per_claim_rows.append({"id": claim["id"], "category": claim["category"], "error": str(e)})
            continue

        field_scores = score_extraction(claim["ground_truth"], result["extracted_fields"])
        claim_field_accuracy = sum(field_scores.values()) / len(field_scores) if field_scores else 0.0
        all_field_results.extend(field_scores.values())

        is_decision_correct = result["decision"] == claim["expected_decision"]
        decision_correct += int(is_decision_correct)

        hallucinated_fields = check_hallucination(result["extracted_fields"], claim["ground_truth"], claim["email_text"])
        if hallucinated_fields:
            claims_with_hallucination += 1

        latencies.append(result["latency_ms"])

        cost = None
        if result["token_usage"]:
            usage = result["token_usage"]
            cost = (usage.get("input", 0) / 1000 * PRICE_PER_1K_INPUT_TOKENS
                    + usage.get("output", 0) / 1000 * PRICE_PER_1K_OUTPUT_TOKENS)
            costs.append(cost)

        escalation_predicted += int(result["escalated"])
        escalation_expected += int(claim["expected_escalation"])

        per_claim_rows.append({
            "id": claim["id"],
            "category": claim["category"],
            "field_accuracy": round(claim_field_accuracy, 3),
            "decision_correct": is_decision_correct,
            "predicted_decision": result["decision"],
            "expected_decision": claim["expected_decision"],
            "hallucinated_fields": hallucinated_fields,
            "escalated_predicted": result["escalated"],
            "escalated_expected": claim["expected_escalation"],
            "latency_ms": round(result["latency_ms"], 1),
            "cost_usd": round(cost, 5) if cost is not None else None,
        })
        print(f"field_acc={claim_field_accuracy:.0%} decision_ok={is_decision_correct} {result['latency_ms']:.0f}ms")

    n = len([r for r in per_claim_rows if "error" not in r])
    extraction_accuracy = (sum(all_field_results) / len(all_field_results)) if all_field_results else 0.0
    decision_accuracy = decision_correct / n if n else 0.0
    hallucination_rate = claims_with_hallucination / n if n else 0.0
    escalation_rate = escalation_predicted / n if n else 0.0

    lat_sorted = sorted(latencies)
    p50 = lat_sorted[len(lat_sorted) // 2] if lat_sorted else 0
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)] if lat_sorted else 0
    mean_latency = statistics.mean(latencies) if latencies else 0
    mean_cost = statistics.mean(costs) if costs else None

    # Escalation precision/recall against the categories designed to need it
    escalation_tp = sum(1 for r in per_claim_rows if r.get("escalated_predicted") and r.get("escalated_expected"))
    escalation_fp = sum(1 for r in per_claim_rows if r.get("escalated_predicted") and not r.get("escalated_expected"))
    escalation_fn = sum(1 for r in per_claim_rows if not r.get("escalated_predicted") and r.get("escalated_expected"))
    esc_precision = escalation_tp / (escalation_tp + escalation_fp) if (escalation_tp + escalation_fp) else 0
    esc_recall = escalation_tp / (escalation_tp + escalation_fn) if (escalation_tp + escalation_fn) else 0

    with open(out_dir / "eval_results.csv", "w") as f:
        f.write("id,category,field_accuracy,decision_correct,predicted_decision,expected_decision,"
                "hallucinated_fields,escalated_predicted,escalated_expected,latency_ms,cost_usd\n")
        for r in per_claim_rows:
            if "error" in r:
                continue
            f.write(f"{r['id']},{r['category']},{r['field_accuracy']},{r['decision_correct']},"
                    f"{r['predicted_decision']},{r['expected_decision']},"
                    f"\"{';'.join(r['hallucinated_fields'])}\",{r['escalated_predicted']},"
                    f"{r['escalated_expected']},{r['latency_ms']},{r['cost_usd']}\n")

    report = f"""# ClaimPilot Evaluation Report

Evaluated on **{n} test claims** ({len(testset) - n} failed to process).

## Headline numbers (for the resume bullet)

Evaluated on {n} test claims, achieving **{extraction_accuracy:.1%}** structured-field
extraction accuracy and **{decision_accuracy:.1%}** decision accuracy.

## Full metrics

| Metric | Value |
|---|---|
| Structured-field extraction accuracy | {extraction_accuracy:.1%} |
| Decision accuracy | {decision_accuracy:.1%} |
| Hallucination rate (claims with ≥1 unfounded field) | {hallucination_rate:.1%} |
| Human escalation rate | {escalation_rate:.1%} |
| Escalation precision | {esc_precision:.1%} |
| Escalation recall | {esc_recall:.1%} |
| Mean latency | {mean_latency:.0f} ms |
| p50 latency | {p50:.0f} ms |
| p95 latency | {p95:.0f} ms |
| Mean cost/request | {f'${mean_cost:.4f}' if mean_cost is not None else 'not tracked — add token_usage to API response'} |

## By category

"""
    categories = sorted(set(r["category"] for r in per_claim_rows if "error" not in r))
    report += "| Category | n | Field accuracy | Decision accuracy |\n|---|---|---|---|\n"
    for cat in categories:
        rows = [r for r in per_claim_rows if r.get("category") == cat]
        cat_field_acc = statistics.mean(r["field_accuracy"] for r in rows)
        cat_dec_acc = sum(r["decision_correct"] for r in rows) / len(rows)
        report += f"| {cat} | {len(rows)} | {cat_field_acc:.1%} | {cat_dec_acc:.1%} |\n"

    (out_dir / "eval_report.md").write_text(report)
    print("\n" + report)
    print(f"Saved: {out_dir/'eval_report.md'}, {out_dir/'eval_results.csv'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--testset", type=str, default="claims_testset.json")
    ap.add_argument("--out", type=str, default="./eval_out")
    args = ap.parse_args()

    with open(args.testset) as f:
        testset = json.load(f)

    run_eval(testset, Path(args.out))