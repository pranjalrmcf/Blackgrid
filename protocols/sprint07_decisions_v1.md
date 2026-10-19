# Sprint 7 decisions-v1 — frozen before numerical execution

Date: 19 October 2026. Authorization: user requested Sprint 7 implementation.
This protocol is synthetic only, CPU, offline, USD 0; no existing test windows
are reused as unseen evidence. No probability-display permission for real forecasts.

## Registered distributions and partitions

Decision model: two fixed methods A/B, independent Bernoulli success streams
on independent simulated tasks. Success means the registered binary task succeeds;
this analytic plumbing example is not an AP improvement or a graph-algorithm benchmark.
Per episode the evaluator samples theta_A/theta_B independently Uniform(0,1).
Controller receives sampled outcomes only through a trusted callable; truth is never
in a planner payload. Prior Beta(1,1); sensitivity Beta(0.5,0.5), Beta(2,2).
Terminal reward is success on one future task (1 or 0); experiment cost 0.02
artificial utility units. Sensitivity costs 0.01 and 0.04. Ten steps maximum.
Exact one-step EVSI; stop on nonpositive net value; ties A before B.
Policies: stop, fixed alternating ten steps, seeded random ten steps, posterior-mean
greedy ten steps, myopic EVSI. 100 independent evaluator episodes, seeds 71000..71099;
development seeds 70000..70009; predictive checks 72000..72199. Common potential
outcome streams indexed by episode, method and attempt, never visible to policies.
Evaluate expected terminal success minus cost, realized future success minus cost,
terminal expected regret, steps, failures, useful-answer coverage and elapsed time.
No superiority acceptance threshold: report all outcomes, including negative ones.

Calibration correctness demonstration: independent synthetic temporal graphs,
30 nodes, all 435 undirected candidate pairs; five consecutive synthetic periods.
Each pair has a fixed history-available covariate x~Normal(0,1), and independent
period outcomes Bernoulli(sigmoid(-2 + 1.2*x)). This is a declared event generator,
not timestamps attached to a static graph. All candidates are retained.
Periods: 0 train, 1 selection (one fixed logistic configuration), 2 sigmoid fit,
3 assessment, 4 final test. No tuning. 30 independent graphs, seeds 73000..73029.
Training-only standardization, logistic C=1, max_iter=300; sigmoid calibrator
C=1000000, max_iter=300. Reject nonconvergence/degenerate fit labels.
Ten equal-width reliability bins, sparse if n<30. Log-loss clipping 1e-12.
Report Brier/log loss, prevalence reference, AP, AUC, bins and score extrapolation.
No probability-display eligibility criterion is registered: display remains disabled.
Graph-level paired percentile bootstrap of calibrated-minus-raw Brier: 1000 resamples,
seed 74000, 95% interval. No pair bootstrap or CI on existing CollegeMsg windows.
Separate bootstrap behavior study: seeds 74100..74199, 30 independent Normal(0,1)
graph-summary differences, 1000 resamples each. Report empirical coverage, not guarantee.

Bayesian checks: 200 independent prior-predictive simulations (72000..72199),
20 observations and held-out blocks of ten; report parameter credible coverage and
held-out block predictive coverage, including all three priors. No tuning from results.
Posterior predictive block tail <0.01 triggers limitation/stop in the demo.

Causal example: seeds 75000..75099; 500 independent graph-level units per seed.
X~Normal(0,1), T~Bernoulli(0.5) randomized, Y=2*T+1.5*X+Normal(0,1).
ATE=2, no cross-unit interference. Compare naive and adjusted OLS/g-computation;
report mean bias/RMSE and all attempts. Separate refusal fixtures for collider
adjustment, positivity failure, hidden confounding and unsupported interference.
The DAG gate checks the supported backdoor setting; assumptions are never verified
from the diagram. Real CollegeMsg causal claims abstain.

## Execution and evidence

Trusted registered Python only, no arbitrary generated code or external model.
Cooperative tool deadline 120s; comparison deadline 1800s; total 3600s; bounded
array sizes; process memory stop at 2 GiB where measurable. No OS sandbox claim.
Cancellation marker checked between operations; unknown/missing evidence fails closed.
Immutable protocol/hash and source/dependency/config hashes in run manifest.
SQLite operations hold deduplicated observations and hash-bound artifacts; replay
verifies hashes and never calls the outcome source. Preserve sanitized failure status.
The trusted local evaluator owns simulator truth; no agent/service receives it.
This is information separation for trusted tools, not hostile-process isolation.

Bayesian optimization gate: unmet. No expensive search is defined; skip.
Required initial slice: exact belief update, one worthwhile experiment, one stop.
Later branches may remain partial if execution/verification gates are not met.

References: SciPy beta distribution documentation; scikit-learn probability
calibration documentation; SPRINT_07.md. Frozen choices above are project choices.
