# Sprint 6 prediction protocol: prediction-v1 (FROZEN)

**Frozen:** 18 October 2026. It was frozen after the rights and dependency decisions (D-070) and before any CollegeMsg
forecasting score or metric was computed. The evaluation run records this file's sha256.

**Inspected before freezing**, and disclosed here: a history-only capacity preflight on CollegeMsg (D-071).
- **Seen:** candidate counts at b2–b9, plus label *counts* (positives and cold-start) for development and validation
  cutoffs b2–b7 only.
- **Not seen:** any score, any metric, any test-period (b8, b9) label or label count.
- **Consequence, fixed before results:** `new_pair` has 5,333,254 supervised development rows, above the 2,000,000
  cap. Its logistic model is therefore a recorded **capacity stop**, not sampled. `repeat_pair` (44,901 rows) trains
  normally.

## 1. Question and tasks

> Which previously unconnected pairs are most likely to exchange a message in the next forecast window, and does
> using recent activity improve the ranking?

**Data treatment:** pairs are known-node and undirected; an event in either direction is a pair interaction, so
sender and recipient roles are discarded. Raw events keep their direction and timestamps.

**Window:** for cutoff `t` and horizon `H`, history is the events with timestamp `< t`, and labels come from
`[t, t + H)`. Events at exactly `t` are future events, and timestamp ties never straddle a cutoff.

| Task | Eligible pairs | Positive |
|---|---|---|
| `new_pair` (primary) | distinct historical nodes with no historical interaction | at least one event in the horizon |
| `repeat_pair` (secondary) | distinct historical pairs that have interacted | at least one event in the horizon |

**Labels:**
- No event in the horizon means *no observed interaction*.
- A pair whose event falls beyond the horizon is a valid zero.
- Self-pairs are excluded and counted.

**Cold start:** future pairs with an endpoint unseen before `t` are excluded and counted, reported as
`cold_start_positive_pairs_excluded`. This is a transductive task; there is no coverage claim for new nodes.

## 2. Splits (elapsed time, fixed before any result)

**Boundaries:** `t0` = minimum validated timestamp; `t_end` = maximum + 1 s; `D = t_end − t0`;
`b_i = t0 + floor(i·D/10)`; `b_10 = t_end`; `H = D/10`.

| Role | Cutoffs (each predicts its next bin) |
|---|---|
| Supervised development | b2, b3, b4, b5 |
| Validation (selection only) | b6, b7 |
| Sealed test | b8, b9 |

**Forecasting rules:**
- Forecasts are fixed-origin within a horizon.
- At b9, features and candidates are refreshed from history, with no retraining, retuning or inspection of b8
  scores before both test forecasts are saved.
- If timestamps or label counts make the task unsuitable, stop and report. Do not move cutoffs.

## 3. Candidates and ties

- The complete eligible universe is streamed in batches of 50,000.
- **Cap:** 2,000,000 candidates per task/cutoff and 2,000,000 supervised rows. Exceeding it is a recorded capacity
  stop, never sampling.
- No balanced negatives.
- One shared seeded tie-break hash of canonical pairs (`seed = 0`) is used by every method. Tie rates are reported.
- **Diagnostic for `new_pair`:** results with and without a historical two-hop path, using the same predictions.

## 4. Methods (one configuration each unless stated)

| Stage | Methods |
|---|---|
| Controls | seeded random (`seed = 7`), constant |
| Structural | Common Neighbors, Jaccard, Adamic–Adar (natural log), Resource Allocation, Preferential Attachment, all on the cumulative simple graph before `t` |
| Temporal | recent-activity product and recent-window Resource Allocation, windows `H` and `2H`; for `repeat_pair` only, pair frequency and pair recency (score = −(t − last pair event)) |
| Supervised (Session 4) | L2 logistic regression, `C ∈ {0.1, 1, 10}`, 200-iteration cap; nonconvergence counts as a failed configuration |

**Logistic regression features:**
- the five structural scores;
- endpoint cumulative degree and `H`-window activity, as symmetric sum and product;
- for `repeat_pair`, pair count and recency, with an unseen-recency indicator;
- `log1p` applied to counts;
- scaling fitted on development rows only.

**Implementation pending:** this needs the dependency decision.

**Selection:** on mean validation AP over b6 and b7, separately per task, choose the strongest non-temporal reference
and the strongest temporal method. Freeze both before the test.

**Not in scope:** GNN; any GNN needs the separate gate in SPRINT_06.md §6.

## 5. Metrics

- **Primary:** average precision over the complete universe, per task and cutoff, with positives, candidates and
  prevalence.
- **Secondary:** Precision@K and Recall@K with `K = min(100, candidates)`; ROC-AUC (supplementary, tie-aware).
- A zero-positive cutoff is *not evaluable*. Both validation cutoffs must be evaluable to select a winner.
- Report means and paired differences. There is no bootstrap over pairs and no significance or generalization claim.
- Scores are uncalibrated rankings, never probabilities.

## 6. Budgets and stopping

**Budgets:**
- 120 s and about 1 GiB per task/cutoff/method.
- For the whole real-data comparison: 60 min, at most 30 fitted configurations, 2 GiB.
- Memory is not OS-enforced on Windows, so these are planned limits, measured and reported, not a sandbox.

**Stop on:** exhaustion, leakage, malformed data, unresolved rights, attempted test-label access, or unknown pricing.

**Spending:** USD 0 for numerical work. Any LLM explanation uses the existing allowance; nothing is reset or enlarged.

## 7. Rights gate

D-003 covers local non-commercial Sprint 1 analysis only. A recorded decision for Sprint 6 forecasting is required
before any CollegeMsg processing under this protocol. Raw or pair-level outputs are never redistributed.

## 8. Execution details fixed at freeze

- **Order, enforced in code** (`blackgrid.prediction.suite`):
  1. validation metrics for every method and logistic configuration;
  2. selection, written to `selection.json`;
  3. test forecasts for all prespecified methods, saved as hashed local arrays (`predictions_manifest.json`);
  4. only then are test labels read and metrics computed. A changed prediction file stops the evaluator.
- **Selection:** the logistic model counts as a *temporal* candidate, since it uses recent-activity features. Ties
  go to the earlier registered method (simpler first), then the smaller `C`.
- **Refit:** if a logistic model is selected, it is refitted once on development and validation snapshots (labels
  end by b8), with the same `C`.
- **Reporting:** test metrics are reported for every prespecified method. The headline comparison is
  selected-temporal minus selected-static AP at b8 and b9, plus their mean. For `new_pair`, the two-hop / no-two-hop
  diagnostic is reported on the selected methods.
- **Artifacts:** pair-level score arrays stay in the local run folder (`runs/`, git-ignored). Only aggregates are
  exported to `results/`.
