# ClaimPilot Evaluation Harness — Quick Start

Two scripts:

1. **`generate_synthetic_claims.py`** — builds a 100-claim labeled test set
   (60 clean, 15 duplicate, 15 weather-mismatch, 10 ambiguous/missing-info).
2. **`eval_harness.py`** — runs that test set through your deployed
   ClaimPilot API and scores it.

## 1. Install extras

```bash
pip install requests rapidfuzz openai
```

## 2. Generate the test set

Uses the same Gemini-via-OpenAI-compatible-endpoint setup as ClaimPilot itself
(see `_env.example`):

```bash
export LLM_API_KEY=your-google-ai-studio-key
# optional — these already default to the values in _env.example:
# export LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
# export LLM_MODEL=gemini-2.0-flash
python generate_synthetic_claims.py --n 100 --out claims_testset.json
```

Skim the output file afterward — spot-check 5–10 claims by hand to confirm
the ground truth actually appears in the generated email text before you
trust the scores that come out the other end.

**Weather-mismatch claims need one manual step:** for each `weather_mismatch`
claim, use your own Open-Meteo integration (or the API directly) to confirm
that no hail/severe weather occurred at that location on that date. That
confirmation is what makes it a valid fraud-check test case rather than a
coin flip.

## 3. Wire up the harness to your API

Open `eval_harness.py` and edit the two marked sections:

- `call_claimpilot()` — request payload your `/api/claims/process` (or
  whatever your endpoint is called) actually expects.
- The `RESPONSE FIELD MAP` block — the JSON keys your response actually
  uses for extracted fields, decision, escalation flag, and token usage.

If your agents don't currently return token usage in the API response,
either add it (cheap: just pass through what the LLM client returns) or
leave cost/request out of the bullet — don't estimate it, since a made-up
cost number is worse than no cost number.

## 4. Run it

```bash
python eval_harness.py --testset claims_testset.json --out ./eval_out
```

This produces:

- `eval_out/eval_report.md` — the headline sentence plus a full metrics
  table and a per-category breakdown
- `eval_out/eval_results.csv` — one row per claim, for spot-checking
  failures or building a chart

## 5. Sanity-check before you trust the number

- Read through every claim your harness marked "decision incorrect" —
  confirm the harness's expected label was actually right, not just your
  system's output was wrong. Synthetic ground truth can be wrong too.
- If extraction accuracy comes back suspiciously high (>98%) on the first
  run, check `FUZZY_MATCH_THRESHOLD` and `values_match()` — a threshold
  that's too loose will pass near-misses.
- Re-run once after fixing anything found above. Report the accuracy from
  that clean run, not the first one.

## 6. Write the bullet

Once you trust the numbers, drop the actual figures into:

> Evaluated on 100 synthetic test claims, achieving **X%** structured-field
> extraction accuracy and **Y%** decision accuracy, with a **Z%** human
> escalation rate on ambiguous cases and p95 latency of **N ms** per claim.

Use real numbers only — if a metric came out worse than expected, that's
still worth including (e.g. "identified a 12% hallucination rate on
free-text fields, which motivated adding a validation agent") — it reads
as engineering maturity, not a weakness.
