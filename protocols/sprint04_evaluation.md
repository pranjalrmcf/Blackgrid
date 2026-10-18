# Sprint 4 exploratory evaluation protocol: s4-v1

**Frozen:** 18 October 2026. Frozen before any s4 case was generated and before any s4 outcome was seen. The suite
records this file's hash in its freeze receipt and stops if this file, or any source file, changes during execution.

**Status:** exploratory. No confirmatory hypothesis, improvement margin or efficacy claim is registered. Results test
engineering behaviour under scripted mock and rule roles. They say nothing about how well a real model works.

**Reviewer basis:**
- Claim-support standards follow `review-rubric-v1`.
- The reference reviewer was Codex_AI (D-058). The user waived the human-review gate (D-059), so no human has
  validated these standards. Scores are labelled *AI-reviewed rubric*, not human-validated.

## 1. Cases

**IDs:** 24 new IDs, `val-101` to `val-124`. Sprint 3's `val-001`–`val-024` are development and regression evidence
only and are not reused here.

**Neutral index:** i = id − 100.

**Families and parameters:**
- Identical to Sprint 3 (`protocols/sprint03_evaluation.md`), in blocks of three: strong SBM, weak SBM, random
  G(n,m), uneven degrees, disconnected, masked SBM.
- i = 19–24 are refusal tasks on G(20,35): odd i is an invalid-method request, even i is a causal request.
- **Disclosed reuse:** every generator family and parameter is reused. Only the instances (seeds) are new. No claim
  about unseen families follows from fresh seeds.

**Seeds:**
- Generator seed for case i ≤ 18 is 3001 + 100·(i−1), giving 3001–4701. The disconnected family also uses seed+1 to
  seed+3.
- Refusal cases use 8100 + (i−18), giving 8101–8106.
- All seeds lie in the val range and are disjoint from Sprint 3 (1001–2704, 8001–8006) and from development.
- Master experiment seed: 40000 + i.

**Overlap check:** before any investigation, compare projection hashes against the 8 development cases and the 24
Sprint 3 validation graphs. Any exact overlap stops the suite.

**Experiment spec per case:** the same as Sprint 3.
- Louvain, five restarts, resolution 1.
- 99 degree-preserving nulls, 10 swaps per edge, the existing suitability rules.
- Three 10%-uniform edge-removal replicates with 99 nulls each.

**Role isolation:** agent roles receive only the neutral question, the request, the graph and its GraphRecord.
Families, parameters, labels, hidden edges and expectations stay evaluator-only.

## 2. Arms (matched inputs, same workflow, same limits, no tool cache)

1. **`baseline`: deterministic rule baseline**, `RuleBaselineProvider`, with no model of any kind.
   - Planner: refuses non-allowlisted methods and causal requests; otherwise the fixed three-tool plan.
   - Analyst: exactly two templated claims taken from saved evidence, plus the flags from the saved report.
   - Runs under the `validated` condition, so the plan validator and critic (also deterministic rules) apply.
2. **`tool_only`:** the scripted naive mock (`MockProvider`), with no plan validator or critic.
3. **`validated`:** the same mock, with plan validator, critic-v3 and reviser.

**Order:** serial, per case: baseline, tool_only, validated.

**Budget:** mock and rule roles only, USD 0, a 3,600-second total cooperative budget and the existing per-run limits.

**Stopping:**
- Stop when the budget is exhausted or an overlap is detected; save a partial outcome.
- A failed run stays in the denominator. Nothing is retried or rerun inside the suite.

## 3. Scoring: evaluator `s4-eval-v1`

The evaluator is independent of `critic.py` and `pilot.py`. It reuses the s3-eval-v1.1 artifact checks: manifest
hashes, Monte Carlo recomputation and the verdict rule.

Claim forms are a frozen whitelist. Anything else is **unassessed**, never accepted.

| Form | Primary scoring | Sensitivity scoring |
|---|---|---|
| `Modularity Q = a versus a degree-preserving null mean of b (p = c).` | supported if all three numbers bind to their cited fields | same |
| `Under the preregistered rule the verdict is 'v' for this graph only.` | **unsupported**: "preregistered" is not established by the cited field (D-058) | supported if v equals the cited and recomputed verdict (the s3 rule) |
| `The saved decision-rule verdict is 'v' for this graph only.` | supported if v equals the cited and recomputed verdict | same |
| `Observed modularity exceeds the null mean of b (p = c).` | supported only if observed Q, null mean and p are all cited, Q > mean, and p ≤ 0.05; otherwise unsupported (one-sided or misleading) | same |
| contains `strong community structure` | unsupported | same |
| causal wording | unsupported (negated causal wording is unassessed) | same |

The primary and sensitivity scorings differ **only** in the "preregistered" row. Both are reported. That
disagreement is unresolved and is not tuned away.

**Useful answer:** the s3 definition. Complete verified artifacts, an evidence-consistent verdict, the required flags,
no unsupported or unassessed claim, and at least one claim unless the task is a refusal or an abstention.

## 4. Metrics (per arm, all 24 cases in every denominator)

- Unsupported/assessed claims and the macro fraction per graph; unassessed counts; zero-claim cases.
- Useful complete answers.
- Positive-answer coverage: useful answers on cases whose recomputed evidence verdict is `supported`. This is not
  recall of planted labels.
- Correct refusals; abstentions; failures; missing analyses.
- Calls, tokens, cost (USD 0), wall time.
- Paired differences (validated − tool_only, validated − baseline) for the useful fraction and the macro unsupported
  fraction, with 2,000 paired graph bootstrap draws (seed 7351) and percentile 95% CIs, for this case mix only.
- A lower unsupported rate reached by omitting useful answers does not count as an improvement. Coverage is always
  reported next to it.

## 5. Reproduction (Session 6, item 6)

- Run the offline test suite in a fresh, locked environment created from `uv.lock` in a temporary copy of the tracked
  sources (`git archive HEAD`).
- Reproduce one mock first-window investigation there and compare its scientific fingerprint (Q, null mean, p,
  verdict, sensitivity agreement) with the uncached run in the working tree, and with a cached rerun.
- Tolerated nondeterminism: timestamps, run IDs, elapsed times and file paths.

## 6. Limitations stated before execution

- The mock's mistakes are scripted, and the reviser's output is fixed. This can favour the validated arm.
- The baseline was designed knowing the whitelist, so its claim forms are guaranteed to be assessable.
- critic-v3 was written knowing Sprint 3's claim forms.
- One AI reviewer set the claim standards, with no human review.
- Synthetic results are kept separate from CollegeMsg findings.
