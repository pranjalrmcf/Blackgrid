# Sprint 6 report: baseline-first temporal link prediction

**Date:** 18 October 2026.
**Protocol:** `protocols/sprint06_prediction_v1.md`, frozen before any CollegeMsg score.
**Run:** `runs/sprint6-v1`, local only. Aggregates are in `results/sprint06-v1/summary.json`.
**Cost:** USD 0, with no LLM calls. Wall time was 72 s and peak memory 534 MB, measured in the clean reproduction; the
original run's memory reading failed, as noted below.

## What can now be done

An authorized user can run a reproducible, known-node forecast of who will message whom in the next 19.37 days:

```
blackgrid predict-eval configs/collegemsg_full.json --output runs/NEW   # frozen retrospective evaluation
blackgrid forecast configs/collegemsg_full.json --evaluation runs/sprint6-v1 --task new_pair
```

The results appear in the console as **Forecast connections**. The page shows the task, the history date, the
horizon, the method, statements checked by the predictive claim checker, the sealed-test evaluation table, and the
locally ranked pairs.

## Sessions and acceptance

| Session | Delivered | Acceptance evidence |
|---|---|---|
| 1 Protocol and contracts | Tasks, splits, candidate rules, rights (D-070), budgets; frozen protocol | The future-mutation test passes; protocol hash recorded |
| 2 Temporal pipeline | History strictly before the cutoff, horizon labels, cold-start counts, aggregate manifests | Boundary, tie, repeat, reversal, self-loop and cold-start tests |
| 3 Traditional baselines | Controls; CN, Jaccard, AA, RA, PA, streamed over the complete universe | Matches the networkx reference on triangle, path, star and disconnected graphs; hand-computed metrics |
| 4 Temporal and tabular | Recent activity, recent RA, pair frequency and recency; L2 logistic (`C ∈ {0.1, 1, 10}`) | Training-only scaling; nonconvergence counts as failure; capacity stop tested |
| 5 Predictive evaluation | A trusted, ordered evaluator with selection frozen before the test | A test-label spy shows every test label was read after the prediction freeze; a tampered prediction is rejected |
| 6 Product integration | Three typed tools, `pred-critic-v1`, forecast CLI, console Forecast view | The planner cannot move cutoffs, read labels or name unregistered methods; claims are checked; the view was checked in a browser |
| 7 Reproduction | A clean offline copy built from `uv.lock` | 357 passed, 1 skipped (optional `leidenalg`); the rerun is identical, including prediction-array hashes |

**Tests:** 46 new prediction tests. Full suite: 358 passed in the working tree; 357 passed + 1 skipped in the clean environment.

## Results (exploratory; two held-out windows of one network)

The 193.7 days of data were split into 10 windows of 19.37 days each.

**New connections**
- Candidate universe: about 1.7M pairs at each test cutoff, with a prevalence of 5.5e-5 (94 and 96 positives).
- Selected on validation: static = **Preferential Attachment**; temporal = **Recent Activity Product (2H)**.
- The logistic model was a **capacity stop**: 5.33M training rows exceeded the 2M cap. This was recorded before any
  result.

| Test AP | b8 | b9 |
|---|---:|---:|
| Preferential Attachment (static) | 3.9e-4 | 1.07e-3 |
| Recent Activity Product 2H (temporal) | **2.5e-3** | **2.0e-3** |
| Random control | 5.4e-5 | 5.8e-5 |

The temporal method's AP is +0.0015 higher on average. That is about 2–6× the static method and about 40× the base
rate, but in absolute terms these forecasts are weak: Precision@100 is 0.01–0.02.

**Repeat interactions**
- Candidate universe: about 13.6k pairs at each test cutoff, with a prevalence of 0.6–0.9%.
- Selected: static = **Resource Allocation**; temporal = **logistic (C = 10)**. All three logistic configurations
  converged.

| Test AP | b8 | b9 |
|---|---:|---:|
| Resource Allocation (static) | 0.010 | 0.007 |
| Logistic C = 10 (temporal, selected) | **0.401** | 0.137 |
| Pair recency (not selected) | 0.350 | **0.195** |

**Time is strongly informative here:** the selected method is +0.26 mean AP over the static one. However, at b9 the
selected logistic model was beaten by the simpler pair-recency score, which narrowly lost on validation. Selection on
two validation windows is noisy.

## Limitations and honest reading

**Scope of the results:**
- Only two test windows from one network. There is no confidence interval, significance claim or generalization claim.
- The forecasts are associational. Scores are uncalibrated rankings, not probabilities, and they cover known nodes
  only. Cold-start pairs are excluded and counted: 79 at b8 and 51 at b9.
- Direction, message counts within the horizon and timing within the horizon are discarded by the pair task.

**What was seen before freezing:** candidate counts at every cutoff, and label counts for b2–b7 only (D-071). No
score or test label was seen.

**Not done:**
- New-pair supervised learning, because of the capacity stop. A sampled-training protocol would need its own version.
- The real AI is not involved in Sprint 6. The forecast path is deterministic, with a scripted plan, and the tools are
  not wired into the LangGraph planner.
- No GNN; the gate in SPRINT_06.md §6 was not reached.

**Bug found and fixed:** the original run recorded peak memory as `None`. A Windows API call lacked argument types.
This is fixed and tested; the clean reproduction measured 534 MB.

## Next smallest task

Decide whether a versioned sampled-training protocol (prediction-v2) for new-pair logistic learning is worth it. The
alternative is to accept the temporal heuristic and move to the optional real-AI explanation of forecasts under the
existing allowance.

## Addendum: forecasting as agent tools (D-073, D-074)

Forecasting is now part of the main agent and console:
- Ask "Which pairs who have never messaged will message in the next few weeks?" in the console question box.
- The AI planner chooses the forecast tools and the task, and the validator fixes everything else.
- Deterministic code ranks the pairs. The AI only sees aggregates.
- The forecast checker verifies each statement, and the answer page shows the local top pairs.

**Real-AI check:** 3 DeepSeek runs, USD 0.0275 in total.
- Correct task choice for new and repeat questions, with every statement accepted.
- Correctly **refused** a request for probabilities and recommendations.
- One planner reply ignored the 12,000-token reasoning limit (40,576 tokens). The safety reservation absorbed it.

## Addendum: prediction-v2 (rolling evaluation of improvements, D-076)

This run is development evidence: every CollegeMsg window had already been looked at in v1. It was frozen in advance
and run once, with five rolling test windows and models trained only on earlier windows.

| Mean AP over 5 windows | New connections | Repeat messages |
|---|---:|---:|
| v1 winner (recent activity / pair recency) | 0.0044 | 0.270 |
| **logistic_v2** (new features, sampled training) | **0.0076** (won 4/5) | **0.288** (won 4/5) |
| decayed-activity product (new heuristic) | 0.0053 (won 4/5) | 0.094 |
| hgb_v2 (boosted trees; the **pre-registered primary**) | 0.0019 (won 0/5) | 0.254 (won 2/5) |
| random | 0.0001 | 0.011 |

**Pre-registered verdict:** no reliable improvement from boosted trees.

**Secondary finding:** a logistic model on time-decayed features improved on the v1 winners in 4 of 5 windows for both
tasks (about +70% AP for new connections, +7% for repeat messages). This needs confirmation on unseen data before it
can count as a confirmed improvement.
