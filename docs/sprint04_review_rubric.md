# Sprint 4 human claim-review rubric (`review-rubric-v1`)

**Status:** frozen on 2026-10-18, before any reviewer judgments and before any Sprint 4 fresh-evaluation outcome.
**Purpose:** an independent human reference for claim support (SPRINT_04.md Session 1, items 4–5). The rule-based
critic, including the provisional `critic-v3`, is **not** the reference, and it must not be used to fill in this sheet.

## What you review

The file is `results/sprint04-review/review_sheet.csv`. It holds the 81 blinded claims exported by Sprint 3, taken
from `results/sprint03-v1.1/blinded_claims.csv` (sha256 `9bc8d48f…f7fb9ad`).

Each row shows the claim text and the evidence values the claim cited, and nothing else. Hidden from the reviewer:
which case and condition it came from, the generator truth, and the critic's decision. Do not open
`evaluator_private/` or any run folder while reviewing.

These claims were already inspected during Sprint 3 and when Sprint 4 was planned. They are **development evidence**:
they can show how the critic disagrees with people, but they cannot measure how well it works on unseen cases.

## Columns to fill (one row per claim per reviewer)

| Column | Allowed values | Question to answer |
|---|---|---|
| `reviewer` | your initials | Who judged this row. A second reviewer adds their own rows with the same `review_id`. |
| `support` | `supported`, `partly_supported`, `unsupported`, `cannot_judge` | Do the **cited values alone** establish everything the sentence says? |
| `strength_wording` | `ok`, `unsupported`, `n/a` | Does the claim use an effect-strength word ("strong", "clear", "real groups", "weak")? If yes, do the cited values justify it? |
| `comparison_complete` | `yes`, `no`, `n/a` | If the claim compares two things, are **both sides** cited? A test conclusion such as a p-value counts as a side only for inferential wording. |
| `misleading` | `yes`, `no` | Could a careful reader draw a wrong conclusion, even if each number is correct? |
| `confidence` | `high`, `medium`, `low` | How sure you are of this row. |
| `notes` | free text | Your reason. Required for anything except `supported` + `no`. |

## Decision rules

1. **Cited evidence only.** Judge each claim against the values it cites, not against what the run might contain.
   An uncited quantity that the sentence relies on makes the claim `partly_supported` or `unsupported`.
2. **Null tests are not effect sizes.** A small p-value means the observed value is unusual under the null. On its
   own it does not make the structure "strong". Strength words are `unsupported` unless the claim cites an
   explicitly stated threshold.
3. **Literal versus inferential comparisons.**
   - Literal: "Q = 0.38 is above the null mean 0.30". This needs both numbers.
   - Inferential: "stronger than expected under the null". This also needs the test result.

   A literal statement that is true but implies a significant difference when p is large is `misleading = yes`.
4. **Scope.** The claims are descriptive and about one graph only. Generalization, causal wording ("because",
   "drives") or wording about real social groups is `unsupported`.
5. **Refusals and abstentions.** A correct refusal or "inconclusive" statement can be `supported`.
6. **Disagreement is data.** Do not reconcile with another reviewer before both have finished. Record disagreements
   rather than averaging them away.

## After review (not done yet)

- Compare the human labels with the Sprint 3 evaluator and with `critic-v3`, and record every disagreement.
- `critic-v3` was written with knowledge of these claim forms. Agreement on this sheet is therefore a development
  check, not an independent validation. Independent evidence must come from the fresh Sprint 4 cases (Session 6),
  frozen before they are generated.
- Record who actually reviewed and how many rows each person completed. If only one reviewer was available, say so.
