"""
ClaimPilot — Seed Policies for Synthetic Test Claims
------------------------------------------------------
claims_testset.json contains randomly-generated policy numbers that don't
exist in your `policies` table, and `claims.policy_number` has a FK
constraint against it — so eval_harness.py's POSTs to /api/claims fail
with a 500 (foreign key violation) until matching policy rows exist.

This script walks the test set, collects every unique policy_number (all
categories EXCEPT the "ambiguous" claims that intentionally omit it), and
PUTs a policy record for each one via PUT /api/policies, using the same
admin auth flow as eval_harness.py.

Run this once before eval_harness.py, whenever you regenerate the test set:
    export ADMIN_EMAIL="admin@example.com"
    export ADMIN_PASSWORD="12344321"
    python seed_policies.py --testset claims_testset.json
"""

import os
import json
import argparse
from datetime import date, timedelta

import requests

API_BASE_URL = "http://localhost:8000"
LOGIN_ENDPOINT = f"{API_BASE_URL}/api/auth/login"
POLICY_ENDPOINT = f"{API_BASE_URL}/api/policies"

# How far before/after the incident date the policy period should span,
# so the incident always falls safely inside coverage.
POLICY_PERIOD_PAD_DAYS = 365


def fetch_auth_token() -> str:
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if not (email and password):
        raise RuntimeError("Set ADMIN_EMAIL and ADMIN_PASSWORD in the environment first.")
    resp = requests.post(
        LOGIN_ENDPOINT, data={"username": email, "password": password}, timeout=30
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError(f"Login succeeded but no access_token in response: {resp.text}")
    return token


def collect_unique_policies(testset: list[dict]) -> dict[str, dict]:
    """Returns {policy_number: {holder_name, incident_date}} for the first
    claim seen with each policy_number. Skips claims where policy_number
    was intentionally omitted (ambiguous category)."""
    policies: dict[str, dict] = {}
    for claim in testset:
        gt = claim["ground_truth"]
        policy_number = gt.get("policy_number")
        incident_date = gt.get("incident_date")
        if not policy_number:
            continue
        if policy_number in policies:
            continue
        policies[policy_number] = {
            "holder_name": gt.get("claimant_name") or "Test Policyholder",
            "incident_date": incident_date,
        }
    return policies


def build_policy_payload(policy_number: str, info: dict) -> dict:
    if info["incident_date"]:
        incident = date.fromisoformat(info["incident_date"])
    else:
        incident = date.today()
    start_date = incident - timedelta(days=POLICY_PERIOD_PAD_DAYS)
    end_date = incident + timedelta(days=POLICY_PERIOD_PAD_DAYS)
    return {
        "policy_number": policy_number,
        "holder_name": info["holder_name"],
        "holder_email": None,
        "address": None,
        "coverage_limit": 50000.0,
        "deductible": 1000.0,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--testset", type=str, default="claims_testset.json")
    args = ap.parse_args()

    with open(args.testset) as f:
        testset = json.load(f)

    unique_policies = collect_unique_policies(testset)
    print(f"Found {len(unique_policies)} unique policy numbers across {len(testset)} test claims.")

    token = fetch_auth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    ok, failed = 0, 0
    for policy_number, info in unique_policies.items():
        payload = build_policy_payload(policy_number, info)
        resp = requests.put(POLICY_ENDPOINT, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            ok += 1
        else:
            failed += 1
            print(f"  FAILED {policy_number}: {resp.status_code} {resp.text}")

    print(f"Seeded {ok} policies ({failed} failed).")


if __name__ == "__main__":
    main()