# Prediction protocol prediction-v3: confirmation on Bitcoin OTC (FROZEN, confirmatory for one hypothesis)

**Frozen:** 18 October 2026, before any Bitcoin OTC label count, score or metric was computed.
**Data:** SNAP Bitcoin OTC (`snap-bitcoin-otc`, sha256 `76bd9d8f…49ab60c`), authorized in D-077. It is loaded through
`blackgrid.datasets` and has never been used in this project.

**Inspected before freezing** (all history-only or structural):
- the file structure and aggregate profile: 35,592 events, 5,881 users, 90% positive ratings, 2010-11-08 to
  2016-01-25;
- node and candidate counts at b2–b9 under three candidate rules (complete; active in the last H; active in the
  last 2H).

No label, positive count or metric was computed.

## Hypothesis (the only confirmatory claim)

> **H1.** On unseen data, `logistic_v2` (prediction-v2 features, sampled and reweighted training) achieves higher
> average precision than the v1 reference winner in each task.

The v1 reference is the recent-activity product (2H) for `new_pair` and pair recency for `repeat_pair`.

**Decision rule, fixed now, per task:** "confirmed" if the mean paired AP difference over the evaluable origins is
> 0 **and** `logistic_v2` wins at least 4 of the 5 origins. A non-evaluable origin (zero positives) counts as not
won. Otherwise the result is "not confirmed". There is no significance test; this is one network.

## Setup (identical to prediction-v2 unless stated)

**Time:** elapsed-time bins `b0`–`b10`, so H ≈ 190.3 days. Rolling origins b5–b9, with training only on earlier
cutoffs (b2 onward).

**Labels:** a positive is any rating event in either direction during the horizon, regardless of sign or score.
Ratings are attributes and are not used as features in v3. Undirected pairs; known nodes only.

**Candidate rule (new):**
- `new_pair` candidates are pairs among nodes with at least one event in `[t − H, t)` and no prior interaction.
- `repeat_pair` uses all historically connected pairs.
- The rule was chosen **by size only, before any label**:
  - complete universes reach 17.1M pairs, above the 2M cap;
  - the "active in 2H" rule exceeds the cap at b5–b7;
  - "active in H" stays at or below 1.72M.
- Positives that the rule excludes are counted and reported (`excluded_by_candidate_rule`). This defines the
  prediction target as **pairs among recently active users**.

**Everything else is unchanged from prediction-v2:** features, τ = H, the models, negative sampling (5%, weight 20,
seed 11), metrics, tie-break and caps.

## Reporting

- Per task and origin: AP, P@100, R@100, ROC-AUC for every v2 method, plus positives, prevalence and candidate-rule
  exclusions.
- The H1 verdict per task.
- Secondary methods are descriptive only.

## Budget and stopping

- USD 0; no LLM.
- 60 minutes, 2 GiB planned memory.
- Run once into a fresh directory. Do not change anything after seeing results; a new protocol would need new data.
