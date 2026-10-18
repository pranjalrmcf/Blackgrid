# Sprint 4 live pilot protocol: s4-v3 (exploratory)

**Frozen:** 18 October 2026, before any s4-v3 case was generated and before any paid call.
**Authorization (user, verbatim):** "Run the live pilot with deepseek-v4-flash, max $0.50 total".
This covers **one** execution of this protocol. Any rerun or extension needs new authorization.

## 1. Question

Does a real model, `deepseek/deepseek-v4-flash-0731` through OpenRouter, behave differently from a deterministic
template when its tools are constrained? Two comparisons:
- **writer alone** (tool_only), with no plan validator or critic;
- **writer + checker** (validated), with the plan validator, critic-v4 and reviser.

This is exploratory. No confirmatory hypothesis or improvement margin is registered. One run of 24 cases cannot
establish model efficacy, error rates or generalization.

## 2. Cases

**IDs:** 24 new IDs, `val-301` to `val-324`, with neutral index i = id − 300. Families, parameters and tasks are
identical to s4-v1/s4-v2 (`protocols/sprint04_evaluation.md` §1), and that reuse is disclosed.

**Seeds:**
- Generator seed for i ≤ 18 is 7001 + 50·(i−1), giving 7001–7854 including the disconnected family's seed+3.
- Refusal cases use 8300 + (i−18), giving 8301–8306.
- Experiment seed: 60000 + i.

**Overlap check:** exact projection-hash overlap with the development cases and every other registered validation
set stops the suite before any paid call.

**What the model sees:** only the neutral question, the request, an aggregate graph profile, the allowlisted tool
descriptions and the tool evidence. These are synthetic graphs, so no CollegeMsg data or personal data is sent.

## 3. Arms and order

Per case, serially: `baseline` (the rule template, free), then `tool_only` (live), then `validated` (live).

**Settings, the same for both live arms:**
- the D-056 limits: 16,000 output tokens per call and a 240 s request timeout;
- the existing per-run caps: 8 calls, 100,000 tokens, at most 1 retry per call, at most 2 revision rounds;
- no tool cache.

## 4. Money

**Pilot cap: USD 0.50 in total**, for all live calls in this pilot.
- Before each live run, that run's per-investigation cap is set to `min(0.50, 0.50 − pilot spend so far)`.
- Spend is counted from durable operation rows, including any open reservation.
- Every call reserves its worst case before dispatch: estimated prompt plus the full 16,000-token completion, at 2×
  list price. So the pilot total cannot exceed USD 0.50, provided the provider honours `max_tokens` and list prices.

**Stopping:**
- When the remaining pilot budget is below USD 0.03, about two worst-case reservations, every remaining live
  attempt is recorded as `not_run_budget` and kept in its denominator. Free baseline runs still execute.
- If the price is unknown or unconfirmed, nothing is sent.
- A failed call, truncation or malformed reply is recorded, never silently retried beyond the existing one-retry
  policy.
- A billing-unknown pause stops the pilot for reconciliation.

**Accounting:**
- Runs live in the main store (`runs/workflow.sqlite`), so the project cap (USD 10) and the store's current-sprint
  cap (USD 1) keep counting all earlier live spend.
- That cap is still labelled `sprint2`. Keeping that label is stricter than starting a new Sprint 4 total, and no
  total is reset.
- The pilot ledger records the attribution "Sprint 4 live pilot".

## 5. Scoring

1. **Automated, primary:** `s4-eval-v1`, unchanged. It recomputes verdicts, flags, completeness and refusals from saved
   evidence. Its claim whitelist covers only the fixed template forms, so free model prose is scored **unassessed**
   and those cases are not "useful" under this scorer. That is an expected limitation, not a model failure.
2. **Automated diagnostics, descriptive only, independent of `critic.py`:**
   - per claim, whether every number equals a cited value at its displayed precision;
   - whether the claim uses strength wording, causal wording or "preregistered".
3. **Claim support:** every live-arm claim is exported, blinded, to `blinded_claims.csv`, with the case and arm in
   `evaluator_private/`, for review under `review-rubric-v1`. **Pending until a reviewer completes it.**

**Metrics per arm, with all 24 cases in each denominator:**
- evidence-consistent verdicts, correct refusals, required flags, completeness;
- failures, truncations, `not_run_budget` counts;
- claims, number-binding rate and wording-flag counts;
- calls, tokens, USD and wall time.

## 6. Limitations stated before execution

- One model, one sampling run, and default provider routing. Temperature 0 is requested, but the provider does not
  guarantee determinism, so a rerun may differ.
- Same families as earlier development cases.
- The critic and grader rules were written knowing the mock's claim forms.
- Without a completed review, there is no claim-support rate for the real model.
- Synthetic results stay separate from CollegeMsg findings.
