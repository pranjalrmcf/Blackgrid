# Sprint 7 report: a bounded synthetic uncertainty/decision slice

Date: 19 October 2026. User authorized implementation and execution after the
documentation-only plan. Source follows D-082's reorganized packages.

## Delivered

- `analysis/decisions.py`: validated priors/objectives/observations, exact conjugate
  updates, credible quantiles, block predictive probabilities, one-step EVSI,
  deterministic stop/ties, deduplicated SQLite receipts and bounded loop.
- `analysis/reliability.py`: chronological partition validation, sigmoid fitting,
  Brier/log loss/AP/AUC, fixed bins/counts, ranking disagreement, independent-graph
  paired bootstrap and explicit refusal of unjustified intervals.
- `analysis/causal.py`: structured assumptions, supported backdoor DAG check,
  descendant/collider protection and non-identification outcomes.
- `evaluation/sprint7.py`: frozen synthetic comparisons, resource/failure records,
  immutable evidence, source/config/dependency hashes and replay verification.
- `agent/research.py`: aggregate-only mock tool facade and closed evidence-bound
  claim vocabulary. Invented observations, probabilities and interval relabeling
  are not accepted inputs.
- `blackgrid sprint7`, existing-console integration, reliability diagram, belief,
  next-experiment and causal-assumption panels; guide and clean-copy verifier.

SciPy is now declared directly because these modules import it. It was already
in the locked scikit-learn dependency closure; no additional runtime package was
installed into the working environment. A separate clean environment was built
offline from the lock. Existing datasets and historical protocols are unchanged.

## Executed evidence

Protocol `protocols/sprint07_decisions_v1.md` was written before numerical
execution. Initial run `runs/sprint7-v1` is preserved. Integration/reproduction
runs reuse exactly these seeds and are engineering reproductions, not fresh
scientific confirmation. Current demonstration: `runs/sprint7-final`.

### Decision policies: 100 independent simulated episodes

Terminal reward is success on one future independent task; each experiment costs
0.02 artificial utility units. All policies have the same ten-step maximum.

| Policy | Mean experiments | Mean expected net utility | Mean terminal regret |
|---|---:|---:|---:|
| Stop immediately | 0 | 0.5141 | 0.1734 |
| Fixed alternating | 10 | 0.4419 | 0.0456 |
| Seeded random | 10 | 0.4391 | 0.0485 |
| Greedy posterior mean | 10 | 0.4290 | 0.0586 |
| Exact myopic EVSI | 1 | 0.5586 | 0.1090 |

All 500 policy episodes completed. The myopic policy buys less information and
has greater terminal regret than the ten-step policies, but spends less utility.
No globally optimal policy, real scientific-discovery gain or significance claim
follows. The symmetry makes this toy stop after one observation; richer models
and multistep planning are not evaluated. Outcome source owns theta and potential
outcomes; the decision function receives sampled observations only.

### Calibration and uncertainty

Thirty independent synthetic temporal graphs, with all 435 candidates retained
per period, separate train/selection/fit/assessment/test periods. Sigmoid-minus-raw
test Brier difference: **+0.000304**, paired graph-bootstrap 95% interval
**[-0.000267, +0.000829]**. Lower is better: no clear benefit from calibration
in this generator. No product probability-display gate is unlocked.

The separate 100-replicate bootstrap behavior study is recorded in
`reliability.json`; it evaluates independent normal graph-summary differences,
not interval coverage on real temporal networks. Pair resampling is refused.
Existing CollegeMsg windows remain ineligible for a confidence interval.

Two hundred prior-predictive replications for each prior are recorded. Empirical
credible coverage is 0.93–0.94 and held-out block predictive coverage 0.98–0.99
(rounded), conditional on the registered prior/generator. Finite simulation does
not certify nominal coverage under other distributions. The demonstration also
records an actual held-out block posterior predictive check.

### Causality

One hundred randomized synthetic replications, 500 independent graph-level units
each, known ATE=2. Adjusted estimator bias **-0.0115**, RMSE **0.0995**; naive
bias **-0.0076**, RMSE **0.1691**. This is a randomized toy: adjustment improves
precision here, not proof of solving observational confounding. Assumption gates
refuse hidden confounding, positivity failure and unsupported interference;
focused tests also exercise collider/descendant and insufficient-adjustment cases.
CollegeMsg returns **not identified**.

## Verification and resource use

Final full regression: **415 passed in 252.30 seconds**. Thirteen Sprint 7
invariants also passed in the clean environment. The earlier 409-test collection
predated six of the added failure/integration checks.

Clean offline source-copy execution, replay and all 13 focused tests passed.
Beliefs, decisions, reliability, causal and summary JSON matched exactly.
Verification receipts: `runs/sprint7-final-clean-source/verification.json` and
`runs/sprint7-clean-source/verification.json`. The portable verifier checks the
versioned scientific hashes in `results/sprint07-v1/scientific_hashes.json`.
All attempts remain local.

The final numerical workload took about 1.4 seconds after imports and peaked at
about 166 MiB working-set memory. USD 0; no LLM calls, downloads, GPUs or cloud.
Environment setup and regression-test time are separate from that workload.
The first offline environment setup was denied by the filesystem sandbox;
the authorized rerun succeeded. Local preview initially failed under socket
restrictions; an authorized localhost-only server allowed browser verification.
The four panels and reliability plot were inspected in the rendered page;
JavaScript syntax also passed a Node parse check.

## Acceptance scope and limitations

The usable synthetic mock loop, exact belief/decision calculations, honest
reliability artifacts, causal demonstration/refusal, clean reproduction and
existing-console presentation are implemented. Numerical observations are
trusted tool receipts; an external model receives neither raw records nor truth.

This is the initial bounded slice, not every research extension in SPRINT_07:

- The success belief is an analytic Bernoulli-task simulator, not measured
  AP-threshold success of real graph algorithms. Calibration has its own synthetic
  temporal graph generator; the two evidence streams are not pooled.
- The selection period is reserved but there is only one fixed configuration;
  no model search occurs. The calibration demonstration uses known-at-history
  pair covariates, not a new CollegeMsg model or a network contagion simulator.
- Graph bootstrap behavior is checked on a separate simple distribution; AP
  bootstrap coverage and dependent real-time-block inference remain deferred.
- The tool facade inspects the completed loop. Main LangGraph integration was
  subsequently added (see the integration addendum); no live efficacy advantage
  is claimed and arbitrary new experiment execution is not exposed to a model.
- Prior/cost-sensitive recommendations are withheld by the facade. The numerical
  trace retains the registered objective's decision for audit.
- Replay validates/reconstructs completed evidence; crash-resume of an incomplete
  full comparison is not implemented. Failed outputs stay immutable and require
  a new run folder. Existing workflow resume behavior is unchanged.
- Limits are cooperative with bounded arrays and measured peak-memory checks;
  there is no hostile-code sandbox or preemptive resource containment.
- The optional Bayesian-optimization gate is unmet and deliberately skipped.

Next smallest scientific task: preregister a graph-algorithm success outcome and
independent generator streams, then connect that trusted experiment source to the
belief controller. Do not transfer the toy utility results to real forecasts.

## Integration addendum (D-084)

The main question router/planner now supports a research family. Four strict,
empty-argument tools inspect the saved synthetic evidence. The workflow pins its
source manifest before planning; durable tool receipts, exact claim checking,
final reports, synthetic claim provenance and console panels share the existing
workflow. No structural follow-up is accidentally requested for research reviews.

The main CLI completed a five-claim mock research review in
`runs/sprint7-integration/20261018T185550Z-2a5315`. A separate normal-workflow replay
completed at `runs/sprint7-integration-replay/20261018T185638Z-ea67e9`, without new
numerical observations or paid calls. Both source and per-tool artifact identities
are retained. Scope is explicit: inspection of a saved synthetic demonstration,
not newly executed research or a conclusion about the selected CollegeMsg graph.

Fifteen integration tests passed: routing, tool/settings rejection, evaluator-key
refusal, provenance, critic rejection of real-world probability transfer/interval
relabeling, crash/resume without repeated calls/observations, missing reference and
changed-source rejection. The existing 65 focused checks also passed. The clean
source-copy run/replay matched every versioned scientific hash and passed all
28 Sprint 7 numerical/integration checks (`runs/sprint7-integration-clean-verified/verification.json`).
An earlier clean attempt was blocked by sandbox atomic-file replacement rules;
that failed receipt is preserved in `runs/sprint7-integration-clean-source`.

Browser verification exercised the actual main console: selected **Review research
evidence**, started a mock investigation, opened its completed answer and inspected
the **Reliability & decisions** tab. Run: `20261018T190049Z-54821a` under
`runs/sprint7-integration`. It used two scripted role calls and USD 0. The view shows
source identity, synthetic scope, credible intervals, candidate utility values,
stop decision and real-data non-identification. A screenshot is retained locally.

The first broad regression found one literal-string assertion for the forecast
tab filter (429 passed, one failed). Its existing expression was restored while
keeping research tabs on a separate branch. All 32 targeted console/research
checks then passed. This did not change numerical evidence or frozen results.
The final complete regression passed **430 tests in 242.13 seconds**. Console
JavaScript syntax and `git diff --check` also passed (Git reported only existing
line-ending normalization notices).

Versions are prompts-v10, critic-v7/research-v1 and tools-v3/research-v1. Historical
receipts remain unchanged; older paused runs cannot silently adopt new prompts.
No dependency, new dataset, paid allowance or scientific benchmark was added by
this integration. Existing numerical seeds/results are reused as engineering
verification, not fresh scientific validation.
