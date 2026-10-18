# Sprint 4 report: reliable execution and defensible claims

**Date:** 18 October 2026.
**Source:** `42aa5d0`, plus the uncommitted Session 6 work, whose hashes are recorded in `runs/sprint4-v1/freeze.json`.
**Paid spend this sprint:** USD 0. Every Sprint 4 run used mock or rule roles.

## Outcome in one paragraph

The five reproduced gaps (R1–R5) are fixed, and each has a regression test that failed before its fix. A fresh,
frozen evaluation on 24 new synthetic cases ran every attempted case to completion. It shows that critic-v3 stops the
scripted mock's unsupported claims. Under the primary scoring, the validated arm is still worse than a simple rule
baseline, because the critic accepts a wording ("Under the preregistered rule…") that the AI reviewer rejects.
The offline workflow reproduces bit-for-bit in a clean locked environment, with and without the cache.

Note: **no human has reviewed any claim.** The reviewer was an AI (Codex_AI), and the user waived the human gate
(D-059).

## Acceptance against SPRINT_04.md §7

| Deliverable | Evidence | Status |
|---|---|---|
| Worker ownership repair | `tests/test_sprint4.py`: a live owner with a heartbeat aged 1,201 s is not displaced; a crashed owner is recovered without force; a displaced owner's late tool result is not adopted | done |
| Accurate interruption status | Suite `KeyboardInterrupt` gives `interrupted`; an interrupted investigation becomes a resumable `paused/interrupted` and then completes on resume | done |
| Honest method contracts | Greedy and Erdős–Rényi null are rejected by the contract, the tool schema and the executor | done |
| Validated cache | Altered, mismatched, stale, malformed and empty entries are rejected, kept and recomputed; a valid hit equals uncached output; a real CollegeMsg rerun is identical cached vs uncached | done |
| Versioned claim policy | critic-v3 (provisional), `review-rubric-v1`, AI review + comparison (D-057, D-058) | done; **human review waived** |
| Fresh evaluation | `protocols/sprint04_evaluation.md` frozen before generation; 72/72 attempts in the ledger; independent `s4-eval-v1` scores | done |
| Compatibility evidence | First-window mock: Q 0.587, null mean 0.593, p 0.718, `not_supported`, identical to the historical result; full-scope paths covered by `tests/test_full_scope.py`; D-056 token settings kept | done |
| Reproduction | Clean copy + `uv sync --frozen --offline`: 248 passed, 1 skipped (optional `leidenalg` extra not installed); first-window fingerprint identical across clean, uncached and cached runs, including all 499 null values | done |
| Close-out report | This file | done |

**Tests:** the working tree ran 249 passed, executed on 18 October 2026.

## Fresh evaluation (s4-v1, exploratory)

**Run:** `runs/sprint4-v1`, 333 s wall time, 0 suite errors. The exported aggregates are in
`results/sprint04-sprint4-v1/summary.json`.

**Cases:** 24 cases (`val-101`–`val-124`) with new seeds and 0 exact overlaps with development or Sprint 3. The
families and parameters are reused from Sprint 3.

**Arms:** matched inputs, in this order:
- `baseline`: deterministic rule templates, no model;
- `tool_only`: the scripted naive mock;
- `validated`: the mock plus critic-v3.

| Per arm, all 24 cases | baseline | tool_only | validated |
|---|---:|---:|---:|
| Useful complete answers, **primary** | 24 | 0 | **6** |
| Useful, sensitivity (preregistered wording accepted) | 24 | 0 | 24 |
| Unsupported / assessed claims, primary | 0/36 | 45/45 | 18/36 |
| Unsupported / assessed claims, sensitivity | 0/36 | 45/45 | 0/36 |
| Unassessed claims | 0 | 0 | 0 |
| Evidence-consistent verdicts | 24 | 4 | 24 |
| Correct refusals (of 6) | 6 | 0 | 6 |
| Positive-answer coverage (of 4 evidence-supported), primary | 4 | 0 | 0 |
| Failed runs | 0 | 3 | 0 |
| Model or rule calls | 42 | 45 | 60 |
| Tokens (mock estimate) | 36,337 | 40,582 | 66,679 |

**Paired differences, primary scoring.** Graph bootstrap, 2,000 draws, percentile 95% CI, this case mix only:
- Useful fraction:
  - validated − tool_only: +0.25 [0.08, 0.42];
  - validated − baseline: −0.75 [−0.92, −0.58].
- Macro unsupported fraction (18 graphs with claims):
  - validated − tool_only: −0.50;
  - validated − baseline: +0.50.

The intervals are degenerate because the mock is scripted.

### How to read it

- **The critic works on the scripted mistakes.** Every naive claim was rejected or revised, including "strong
  community structure" (R8) and the one-sided "exceeds the null" comparison (R7). The tool_only arm was 100%
  unsupported. The three tool_only failures are invalid-method requests that the naive mock tried to obey.
- **The remaining gap is a single wording.** The reviser always writes "Under the preregistered rule the verdict is X".
  - Primary scoring follows the AI review (D-058): the cited field does not establish "preregistered". That claim
    alone is half of the validated claims, so only the six refusals count as useful.
  - When that wording is accepted (the sensitivity scoring), validated equals the baseline exactly.
  - This disagreement between critic-v3 and the reviewer is reported, not tuned away. Resolving it needs a decision:
    either change the wording or critic, or a human ruling.
- **The baseline matching or beating the agent** is the expected result for a scripted mock. A templated report
  carries the same evidence with fewer calls. Nothing here shows that an LLM adds value.
- **Positive-answer coverage is small.** Only 4 of 18 structural cases had an evidence verdict of `supported`. The
  other strong-family instances were judged `inconclusive`/`not_supported` by the frozen rules, for example because of
  the largest-component rule or masking.

## What did not happen, and limitations

- No human review. The claim standards come from one AI reviewer, who had seen earlier results (D-058, D-059).
- critic-v3 and the baseline templates were written knowing the claim forms. The mock is scripted. None of this
  measures how well a real model works, controls any error rate, or generalizes to unseen families.
- Treating unknown claim forms as "unassessed" inside the critic (Session 5, item 5) is not implemented. The
  independent evaluator does it, and found 0 unassessed claims here.
- No live pilot was run. Sprint 4 spend attribution and ceilings (§5) are undecided, and the store still labels the
  current sprint `sprint2`.
- The ownership check assumes one host. A reused pid errs towards refusing a takeover. Hashes catch accidents, not an
  attacker who controls local files.
- The CollegeMsg findings (first week: `not_supported`; exp-v2-full: exploratory `supported`) stay separate from these
  synthetic scores.

## Next decision

The smallest next task is to resolve the "preregistered" wording. Two options:
1. Change the reviser and analyst templates to the neutral "saved decision-rule verdict" form.
2. Make the critic require a protocol citation for that word.

Either is a new versioned protocol (s4-v2). Rerunning on these already-inspected cases would be development evidence,
not fresh validation. After that, a separately authorized live pilot can measure a real model under the D-056 limits.

## Addendum: s4-v2, the wording fix (D-061)

**What changed** after s4-v1:
- The writer's verdict sentence now reads "The saved decision-rule verdict is 'X' for this graph only."
- critic-v4 rejects any un-negated "preregistered" claim.
- The evaluator is unchanged.

**Fresh run:** `val-201`–`val-224` (`runs/sprint4-v2`, 72/72 attempts, 0 errors, USD 0).

| Per arm, 24 fresh cases | baseline | tool_only | validated |
|---|---:|---:|---:|
| Useful complete answers | 24 | 0 | **24** |
| Unsupported / assessed claims | 0/36 | 45/45 | **0/36** |
| Correct refusals (of 6) | 6 | 0 | 6 |
| Positive-answer coverage (of 3) | 3 | 0 | 3 |
| Failed runs | 0 | 3 | 0 |
| Calls | 42 | 45 | 60 |

**What it shows:**
- The single s4-v1 shortfall is removed, and no other metric got worse.
- The fix was aimed at a known failure, so this is development evidence, not independent proof that the critic works.
- The checked agent now **ties** a template baseline, at 18 extra calls.
- Whether a real model adds anything is the next open question. It needs a separately authorized live pilot.
