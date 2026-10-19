# Most recent live system evaluation

**Historical evaluated snapshot: 23/24 strict passes (95.8%)**, 19 October 2026. This evaluation preceded the final full-regression repairs; those later changes have not received a new 24-case live evaluation. The current regression status is reported [separately](current_test_status.md).

| Category | Passed | Attempted |
|---|---:|---:|
| Community structure | 4 | 4 |
| Centrality | 3 | 3 |
| Cross-community bridges | 2 | 3 |
| Forecasting | 4 | 4 |
| Saved synthetic research | 4 | 4 |
| Unsupported requests | 6 | 6 |
| **Total** | **23** | **24** |

All scenarios were frozen before execution and attempted once. There were no incomplete cases or timeouts. The failed question asked for cross-community degree stability; the planner instead selected ordinary centrality. A later validation change rejects that substitution; it is not counted as a retroactive pass.

The real OpenRouter model was `deepseek/deepseek-v4-flash-0731`. Eighteen supported requests invoked real planning, and four research cases also invoked model writing: 22 receipted model operations. Six unsupported requests were refused by deterministic guards without model calls. Community, structural and forecast summaries used local checked evidence templates; no mock or replay provider was used.

Four separate workers finished the batch in **68.56 s**. Median case latency was **4.36 s**, p90 **18.92 s**, and maximum **28.05 s**. Confirmed batch cost was **USD 0.00747418**, with no new unresolved charges. These are warm-cache engineering measurements, not a cold numerical benchmark or a price guarantee.

Scoring combined independent local checks of hashes, numerical values, evidence links and candidate sets with this assistant's semantic review against the frozen rubric. It was not a human review or a claim of independent graph-level generalization. CollegeMsg data, saved numerical evidence and synthetic studies were reused; predictive models were not newly benchmarked. The UI renderer was excluded. Source hashes remained fixed during execution.

The previous 17/24 evaluation, failed repair attempts and this evaluation remain separate. They were not pooled or rescored. Full private receipts and traces stay under ignored `runs/`; this report and the [minimized summary](../results/current-system-eval-v6/summary.json) contain aggregate information only. Reproduce the methodology from the [frozen protocol](../protocols/current_system_eval_v6.json), with new paid authorization and a new protocol/version rather than overwriting the historical run.
