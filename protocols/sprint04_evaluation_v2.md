# Sprint 4 exploratory evaluation protocol: s4-v2

**Frozen:** 18 October 2026. Frozen before any s4-v2 case was generated. Written **after** the s4-v1 results were
inspected (D-060). The suite records this file's hash and stops if it or any source file changes during execution.

**Status:** exploratory. s4-v1 and its results are preserved unchanged.

## What changed from s4-v1, and why

s4-v1 found a single disagreement. The reviser wrote "Under the preregistered rule the verdict is X". critic-v3
accepted it, but the AI-reviewed rubric rejects it, because no cited artifact establishes that anything was
preregistered (D-058, D-060). Every validated-arm shortfall came from that one wording.

The changes, decided after seeing s4-v1:
1. **Writer wording.** The mock reviser and the analyst/reviser prompts (`prompts-v4`) now state the verdict as
   "The saved decision-rule verdict is 'X' for this graph only." The prompts also tell a model not to call the
   verdict "preregistered" and not to use strength words.
2. **Checker rule.** critic-v4 adds R9: a claim that calls a result "preregistered" is rejected unless the statement
   is negated ("not preregistered"). No artifact can establish registration.

**Not changed:**
- the evaluator: `s4-eval-v1`, byte-identical, including both its primary and sensitivity scorings;
- the rubric (`review-rubric-v1`);
- the arms, metrics, budgets, families, parameters, experiment spec and stopping rules.

All of these are as in `protocols/sprint04_evaluation.md` §2–§4.

## Cases

**IDs and seeds:** 24 new IDs, `val-201` to `val-224`, with neutral index i = id − 200.
- Generator seed for i ≤ 18 is 5001 + 100·(i−1), giving 5001–6704. The disconnected family also uses seed+1 to
  seed+3.
- Refusal cases use 8200 + (i−18).
- Master experiment seed: 50000 + i.

**Overlap check:** projection hashes are compared with the 8 development cases and every other registered validation
case set (Sprint 3, s4-v1). Any exact overlap stops the suite.

**Disclosed reuse:** families and parameters are unchanged, and only the instances are new. No claim about unseen
families follows.

## Interpretation fixed before execution

- The change was designed to remove one known failure, so improvement on that failure is expected. That outcome is
  **development evidence** about wording, not independent evidence that the critic is effective.
- The real check is whether anything else breaks: coverage, refusals, failures, unassessed claims, or new unsupported
  forms.
- The mock and baseline remain scripted. Nothing here measures how well a real model works.
- Claim standards still come from one AI reviewer, with the human gate waived (D-059).
