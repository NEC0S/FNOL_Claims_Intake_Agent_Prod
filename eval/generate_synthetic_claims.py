"""
ClaimPilot — Synthetic Test Claim Generator
--------------------------------------------
Generates a labeled test set of synthetic FNOL (First Notice of Loss) claim
emails for evaluating ClaimPilot's extraction and decision agents.

Key idea: we generate the GROUND TRUTH VALUES ourselves (policy numbers,
dates, amounts, damage types) and then ask the LLM to write a realistic,
messy customer email that CONTAINS those exact values. This gives you
reliable ground truth without hand-labeling 100 claims by hand.

Usage:
    export OPENAI_API_KEY=...          # or set GOOGLE_API_KEY and adjust call_llm()
    python generate_synthetic_claims.py --n 100 --out claims_testset.json

Output schema (one entry per claim):
{
  "id": "claim_001",
  "category": "clean" | "duplicate" | "weather_mismatch" | "ambiguous",
  "email_text": "...",
  "ground_truth": {
      "policy_number": "...",
      "claimant_name": "...",
      "incident_date": "YYYY-MM-DD",
      "incident_location": "City, ST",
      "damage_type": "...",
      "estimated_amount": 0,
      ...
  },
  "expected_decision": "approve" | "deny" | "investigate",
  "expected_escalation": true/false,
  "duplicate_of": "claim_0XX" | null,
  "notes": "why this claim was constructed this way"
}
"""

import json
import random
import argparse
import time
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Points at the same LLM setup ClaimPilot itself uses in production: Gemini
# via its OpenAI-compatible endpoint (see _env.example — LLM_BASE_URL /
# LLM_API_KEY / LLM_MODEL). This keeps the generator's writing style
# consistent with what your extraction agent sees in prod. Values fall back
# to the _env.example defaults so this runs with just an API key set.
# ---------------------------------------------------------------------------
import os
import re
from openai import OpenAI, RateLimitError

_LLM_BASE_URL = os.environ.get(
    "LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
)
_LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
_LLM_API_KEY = os.environ["LLM_API_KEY"]  # required — set this before running
_client = OpenAI(api_key=_LLM_API_KEY, base_url=_LLM_BASE_URL)

# Gemini free tier for gemini-3.1-flash-lite is 15 requests/minute.
# Space calls out so we don't hit the ceiling in the first place.
MIN_SECONDS_BETWEEN_CALLS = float(os.environ.get("LLM_MIN_INTERVAL_SECONDS", "4.5"))
MAX_RETRIES = 5

_last_call_ts = 0.0


def call_llm(prompt: str) -> str:
    global _last_call_ts

    # Throttle: never fire calls closer together than our budget allows.
    elapsed = time.time() - _last_call_ts
    if elapsed < MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)

    for attempt in range(MAX_RETRIES):
        try:
            resp = _client.chat.completions.create(
                model=_LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
            )
            _last_call_ts = time.time()
            return resp.choices[0].message.content.strip()
        except RateLimitError as e:
            _last_call_ts = time.time()
            # Try to honor the server's suggested retry delay if present,
            # otherwise fall back to exponential backoff.
            retry_after = None
            match = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+(?:\.\d+)?)s", str(e))
            if match:
                retry_after = float(match.group(1))
            wait = retry_after if retry_after is not None else (2 ** attempt) * 2
            print(f"  [rate limited] waiting {wait:.1f}s before retry "
                  f"({attempt + 1}/{MAX_RETRIES})...")
            time.sleep(wait + 0.5)  # small buffer past the suggested delay
    raise RuntimeError(
        f"call_llm: still rate-limited after {MAX_RETRIES} retries. "
        "Consider raising LLM_MIN_INTERVAL_SECONDS, upgrading your Gemini "
        "quota tier, or reducing --n."
    )


DAMAGE_TYPES = ["hail", "wind", "flood", "collision", "fire", "theft", "vandalism"]
CITIES = [
    ("Austin", "TX", 30.27, -97.74), ("Denver", "CO", 39.74, -104.99),
    ("Miami", "FL", 25.76, -80.19), ("Chicago", "IL", 41.88, -87.63),
    ("Phoenix", "AZ", 33.45, -112.07), ("Seattle", "WA", 47.61, -122.33),
]
NAMES = ["Jordan Reyes", "Priya Nair", "Marcus Chen", "Emily Sato",
         "Daniel Osei", "Laura Kim", "Hannah Brooks", "Omar Farouk"]


def _base_claim(i: int) -> dict:
    city, state, lat, lon = random.choice(CITIES)
    incident_date = date.today() - timedelta(days=random.randint(2, 45))
    return {
        "policy_number": f"POL-{random.randint(100000, 999999)}",
        "claimant_name": random.choice(NAMES),
        "incident_date": incident_date.isoformat(),
        "incident_location": f"{city}, {state}",
        "damage_type": random.choice(DAMAGE_TYPES),
        "estimated_amount": random.choice([1200, 2500, 4800, 7600, 12500, 21000]),
    }


def make_clean_claim(i: int) -> dict:
    gt = _base_claim(i)
    prompt = f"""Write a realistic first-notice-of-loss email from a policyholder
reporting an insurance claim. It should read like a real customer wrote it
(a bit informal, maybe one typo), NOT a form. It must naturally include
these exact facts somewhere in the text:
- Policy number: {gt['policy_number']}
- Name: {gt['claimant_name']}
- Incident date: {gt['incident_date']}
- Location: {gt['incident_location']}
- Damage type: {gt['damage_type']}
- Estimated damage cost: ${gt['estimated_amount']}
Keep it under 150 words. Do not add a subject line, just the body."""
    return {
        "id": f"claim_{i:03d}",
        "category": "clean",
        "email_text": call_llm(prompt),
        "ground_truth": gt,
        "expected_decision": "approve" if gt["estimated_amount"] < 15000 else "investigate",
        "expected_escalation": gt["estimated_amount"] >= 15000,
        "duplicate_of": None,
        "notes": "Straightforward valid claim, no red flags.",
    }


def make_duplicate_claim(i: int, original: dict) -> dict:
    gt = dict(original["ground_truth"])
    prompt = f"""Write a SECOND, slightly reworded first-notice-of-loss email
reporting the SAME incident as before, as if the customer emailed again a
few days later (maybe worried it didn't go through). It must contain the
same facts: policy {gt['policy_number']}, name {gt['claimant_name']},
date {gt['incident_date']}, location {gt['incident_location']},
damage type {gt['damage_type']}, amount ${gt['estimated_amount']}.
Vary the wording and length from a typical claim email. Under 150 words."""
    return {
        "id": f"claim_{i:03d}",
        "category": "duplicate",
        "email_text": call_llm(prompt),
        "ground_truth": gt,
        "expected_decision": "deny",
        "expected_escalation": False,
        "duplicate_of": original["id"],
        "notes": "Duplicate of an already-processed claim; should be caught by dedup check.",
    }


def make_weather_mismatch_claim(i: int) -> dict:
    gt = _base_claim(i)
    gt["damage_type"] = "hail"
    prompt = f"""Write a first-notice-of-loss email reporting HAIL damage.
Include exactly: policy {gt['policy_number']}, name {gt['claimant_name']},
date {gt['incident_date']}, location {gt['incident_location']},
estimated cost ${gt['estimated_amount']}. Written like a real customer,
under 150 words."""
    return {
        "id": f"claim_{i:03d}",
        "category": "weather_mismatch",
        "email_text": call_llm(prompt),
        "ground_truth": gt,
        # NOTE: for a true test you must verify via Open-Meteo's historical
        # API that no hail/severe weather actually occurred at this
        # lat/lon+date, OR deliberately pick a date/location you've already
        # confirmed had clear weather. That confirmation step is what makes
        # this a valid fraud-check test case.
        "expected_decision": "investigate",
        "expected_escalation": True,
        "duplicate_of": None,
        "notes": "Damage type claimed does not match verifiable weather history for the date/location.",
    }


def make_ambiguous_claim(i: int) -> dict:
    gt = _base_claim(i)
    # Deliberately omit a required field from the source text.
    omit = random.choice(["policy_number", "incident_date", "estimated_amount"])
    partial_gt = {k: v for k, v in gt.items() if k != omit}
    prompt = f"""Write a vague, incomplete first-notice-of-loss email. It should
mention {', '.join(f'{k}: {v}' for k, v in partial_gt.items())} but should
NOT mention the {omit.replace('_', ' ')} at all — the customer forgot to
include it. Keep it realistic and under 120 words."""
    gt_with_missing = dict(gt)
    gt_with_missing[omit] = None
    return {
        "id": f"claim_{i:03d}",
        "category": "ambiguous",
        "email_text": call_llm(prompt),
        "ground_truth": gt_with_missing,
        "expected_decision": "investigate",
        "expected_escalation": True,
        "duplicate_of": None,
        "notes": f"Missing required field ({omit}); should trigger human escalation, not a guessed value.",
    }


def generate(n: int) -> list[dict]:
    n_clean = round(n * 0.60)
    n_dup = round(n * 0.15)
    n_weather = round(n * 0.15)
    n_ambig = n - n_clean - n_dup - n_weather

    claims: list[dict] = []
    idx = 1
    clean_pool: list[dict] = []

    for _ in range(n_clean):
        c = make_clean_claim(idx); claims.append(c); clean_pool.append(c); idx += 1
    for _ in range(n_dup):
        original = random.choice(clean_pool)
        claims.append(make_duplicate_claim(idx, original)); idx += 1
    for _ in range(n_weather):
        claims.append(make_weather_mismatch_claim(idx)); idx += 1
    for _ in range(n_ambig):
        claims.append(make_ambiguous_claim(idx)); idx += 1

    random.shuffle(claims)
    return claims


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--out", type=str, default="claims_testset.json")
    args = ap.parse_args()

    dataset = generate(args.n)
    with open(args.out, "w") as f:
        json.dump(dataset, f, indent=2)

    counts = {}
    for c in dataset:
        counts[c["category"]] = counts.get(c["category"], 0) + 1
    print(f"Wrote {len(dataset)} claims to {args.out}")
    print("Category breakdown:", counts)