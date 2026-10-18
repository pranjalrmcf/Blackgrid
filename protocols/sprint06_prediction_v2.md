# Prediction protocol prediction-v2 (FROZEN, exploratory: development evidence)

**Frozen:** 18 October 2026, before any v2 feature, model or metric was computed on CollegeMsg.
**Request (user):** improve forecasting with "sampled training for new connections, time-decayed and
temporal-triangle features, boosted trees, and rolling evaluation over more windows".

## Disclosure: no untouched test data

prediction-v1 already inspected v1-method metrics on every CollegeMsg window used here:
- **b6 and b7** were validation windows.
- **b8 and b9** were the sealed test windows.
- **b5** labels were development labels.

So **v2 results are development evidence**, not a fresh test. Everything below is fixed now, run once, and reported in
full. Nothing is tuned after seeing v2 results; any later change needs prediction-v3.

## What stays the same as v1

- Tasks: `new_pair` and `repeat_pair`, known nodes, undirected labels.
- Ten elapsed-time bins with horizon `H` (19.37 days), and the history-before-cutoff rule.
- Complete candidate universes in evaluation (never sampled).
- The shared tie-break hash.
- Metrics: AP, P@100, R@100, ROC-AUC.

## Rolling-origin evaluation

- **Test origins:** b5, b6, b7, b8, b9. Each predicts its next bin.
- **Training rows** for origin `b_k` come only from snapshots at cutoffs b2 … b(k−1), whose label windows end by
  `b_k`. Cutoffs are processed in time order, and rows from cutoff `b_k` join the pool only after origin `b_k` has
  been scored.
- **No hyperparameter selection:** every configuration below is fixed in advance.

## Features (all from history before the cutoff; τ = H)

| Group | Features |
|---|---|
| v1 structural | CN, Jaccard, Adamic–Adar, RA, PA |
| v1 temporal | activity product at H and 2H; recent RA at H |
| **New: decay** | per-node decayed activity `A(u) = Σ exp(−(t − tᵢ)/τ)` over u's historical events; product and sum for the pair |
| **New: recency** | per-node last-event recency `R(u) = exp(−(t − last(u))/τ)`; product |
| **New: temporal triangle** | `Σ_z exp(−(t − last(u,z))/τ) · exp(−(t − last(v,z))/τ)` over common neighbours z |
| **New: direction** | per-node sent and received event counts; sum of sent and sum of received for the pair |
| **Repeat only** | pair count, pair recency (s), decayed pair count `Σ exp(−(t − t_e)/τ)`, reciprocity (both directions seen) |

Counts are passed through `log1p`. There are no identity features.

## Methods reported (per task, per origin)

**References from v1:**
- random;
- preferential attachment;
- resource allocation;
- recent-activity product (2H) — the v1 new-pair winner;
- pair recency — the best repeat heuristic in v1 (repeat task only).

**New single-score heuristics:**
- decayed-activity product;
- recency product;
- temporal triangle;
- decayed pair count (repeat task only).

**New models**, trained on all v2 features:
- `logistic_v2`: L2, C = 1, 300 iterations, scaling fitted on training rows only.
- `hgb_v2`: `HistGradientBoostingClassifier` with `max_iter=200`, `learning_rate=0.1`, `max_leaf_nodes=31`,
  `early_stopping=False`, `random_state=0`.

**Sampled, reweighted training for `new_pair`:**
- All positive rows are kept, plus a seeded uniform 5% sample of negative rows per training cutoff (hash of
  pair + cutoff, seed 11).
- Negatives get weight 20 so that the training objective matches the full distribution.
- Cap: 2,000,000 training rows. Exceeding it is a recorded stop.

`repeat_pair` uses all rows, unweighted.

## Primary comparison (fixed now)

Per task, `hgb_v2` versus the v1 reference winner (recent-activity product 2H for `new_pair`; pair recency for
`repeat_pair`):
- the mean paired AP difference over the five origins;
- the number of origins won.

**Secondary:** every method's mean AP and P@100.

**Interpretation rule:** "improved" only if the mean AP difference is > 0 **and** the model wins at least 4 of 5
origins. Otherwise report "no reliable improvement". There is no significance claim.

## Budget

- USD 0; no LLM.
- 60 minutes wall time, 2 GiB planned memory.
- One full feature matrix in memory at a time.
- At most 20 model fits (2 models × 2 tasks × 5 origins).
