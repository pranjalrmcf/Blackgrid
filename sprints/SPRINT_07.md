# BLACKGRID — Sprint 7: uncertainty-aware experimental decisions

**Planning date:** 18 October 2026.<br>
**Status:** documentation only; proposed work, not implemented or evaluated.<br>
**Authorization:** create this plan only. Do not modify code, execute experiments, install dependencies, extend paid allowances or provision resources on the basis of this document.

## 1. Decision: make uncertainty useful for choosing the next experiment

Sprint 7 should help BLACKGRID answer two questions:

> “How much should I trust this result?”
>
> “What should I test next, and is the information worth its cost?”

Build one narrow loop: **inspect evidence → quantify what is supported → compare allowed next actions → execute one bounded experiment if worthwhile → update beliefs → stop or report**.

LLMs interpret questions, propose allowlisted actions and explain artifacts. Trusted numerical Python modules calculate uncertainty, update registered probabilistic models and compute decisions. An LLM's confidence, argument or self-review never substitutes for numerical evidence.

Decision theory is central because it connects uncertainty to action. Bayesian inference supplies a defensible belief update for a deliberately small model; it does not turn every score into a probability. Causal inference begins with an identification gate, not automated causal discovery. Bayesian optimization remains conditional: it is useful only when a genuine expensive search justifies it.

No GNN is required. No broad claim of autonomous scientific discovery follows from a successful bounded loop.

## 2. Current evidence and dependencies

The inspected [Sprint 6 report](../docs/sprint06_report.md) records chronological new-pair and repeat-interaction forecasting, traditional/temporal baselines, local ranked pairs and subsequent integration with the agent. It reports two held-out windows of one network, uncalibrated scores, and a capacity stop for new-pair supervised training. These are reported project results, not experiments reproduced while writing this plan.

Sprint 6's `b8`/`b9` test outcomes are now inspected. Preserve its [frozen protocol](../protocols/sprint06_prediction_v1.md) and results. They may inform development but cannot become a new untouched test for calibration, action selection or optimizer superiority. Creating extra overlapping cutoffs in the same inspected period does not restore a holdout.

The report also records a real-provider reasoning-token overrun absorbed by a safety reservation. Before any live Sprint 7 loop, verify current stop/accounting behavior offline. Do not assume provider token limits are enforceable guarantees. Default all new work to mock/replay, USD 0.

Prior sprint documents and source files remain intact. Implementation must inspect the then-current code and any ongoing Claude changes before editing. This document is a forward plan, not certification that Sprint 6 is defect-free.

## 3. Scope across the five concepts

| Concept | Required Sprint 7 slice | Explicit boundary |
|---|---|---|
| Uncertainty quantification | Calibration diagnostics, paired metric uncertainty when sampling units justify it, model disagreement and abstention | No fabricated confidence intervals or individual probability intervals |
| Bayesian inference | One transparent conjugate belief model on independent synthetic experiment outcomes; posterior and predictive checks | No Bayesian interpretation of p-values, AP scores or dependent graph edges |
| Decision theory | Exact expected-utility/value-of-information controller on a small registered action space; compare with fixed policies | No unrestricted self-directed experiments or invented real-world utility |
| Causal inference | Structured estimand/assumption gate plus one known-truth synthetic example | No causal effect or counterfactual claim from CollegeMsg alone |
| Bayesian optimization | Written gate and optional isolated experiment, after required work | No optimizer added to cheap baseline grids merely for sophistication |

The required vertical slice is **reliability evidence + bounded experiment choice**. Full Bayesian graph modelling, causal network estimation, general Bayesian optimization and deployment recommendations are later work.

## 4. Separate the types of uncertainty

Every interval/diagnostic must name its target, units, assumptions and evidence source.

| Output | Meaning | What it cannot establish |
|---|---|---|
| Bootstrap confidence interval for a metric difference | Repeated-sampling uncertainty under a stated resampling design | Probability that a particular pair will interact |
| Bayesian credible interval | Posterior uncertainty for a registered parameter under its prior and likelihood | An assumption-free guarantee or automatic frequentist coverage |
| Perturbation sensitivity range | Variation under prespecified missingness/edge-removal assumptions | A confidence interval or recovered hidden truth |
| Reliability diagram / proper scoring metrics | Evidence about probability predictions on a specified evaluation population | Calibration on a different time period, prevalence or candidate population |
| Model disagreement | Dispersion of registered predictions/rankings | A measured epistemic uncertainty decomposition |

Epistemic uncertainty concerns imperfect knowledge of a model or its parameters; aleatoric uncertainty concerns variation conditional on the chosen model. Do not claim to identify or cleanly separate them from heuristic disagreement or bootstrap spread. The small Bayesian synthetic example may illustrate posterior uncertainty versus conditional outcome randomness, with this model dependence disclosed. A real graph decomposition is deferred.

### 4.1 Metric uncertainty with dependent data

Never bootstrap individual candidate pairs as independent: endpoints, graph topology and time induce dependence. Default to reporting each temporal window and the paired differences, without a confidence interval if the sampling design is inadequate.

For independent synthetic graph replicates, use graph-level paired bootstrap: resample whole graphs and keep every method's outputs paired within each resample. Proposed protocol: at least 30 independent graph replicates and 1,000 bootstrap resamples, fixed seed, two-sided 95% percentile intervals. Label conclusions as conditional on the generator family. Verify interval behavior in a separate repeated-simulation correctness study; do not assert nominal coverage merely because the bootstrap ran.

For future real-data temporal resampling, require a separately preregistered dependence model and adequate time units. A possible gate is at least 20 nonoverlapping forecast windows and at least 10 effective blocks under a prespecified block length. This is an engineering eligibility rule, not proof of coverage or stationarity. Expanding histories remain dependent; stationarity and serial dependence must be assessed. Until justified, abstain from a real-data confidence interval. Sprint 6's two windows fail this gate.

### 4.2 Calibration: distinguish ranking scores from probabilities

Start with the existing logistic model where available. A sigmoid calibrator may also map one frozen heuristic score to a probability model, but that creates a new fitted model and needs its own evaluation. Do not present raw heuristic scores as probabilities.

Use a chronological sequence of **training → model selection → calibration fit → calibration assessment → untouched final test**. Calibration-fit labels cannot also assess calibration, select the model or tune downstream thresholds. Freeze these partitions, the candidate universe and the evaluated population before any scores. Fit transforms on permitted history/training only. Retain all candidates or a separately justified weighted evaluation design; balanced negatives change the probability target.

Required diagnostics: Brier score and log loss, reliability diagrams with fixed bins and bin counts, prevalence reference, discrimination metrics and temporal breakdown. Proper scoring metrics reflect more than calibration alone; do not infer perfect calibration from a lower Brier score. ECE may be supplementary, with binning sensitivity disclosed; it is not the sole acceptance gate.

Default small-data method: one sigmoid calibrator, fixed before evaluation; no isotonic-versus-sigmoid search on test results. Numerical clipping for log loss must be fixed and recorded. Flag sparse bins, degenerate labels, drift and extrapolation. A calibration procedure completing is not evidence that probabilities are reliable. Define any product probability-display criterion, sample-size requirement and tolerances before assessment; otherwise retain **uncalibrated score** labels.

No untouched CollegeMsg calibration/test sequence is currently established by the inspected report. Use synthetic correctness checks first. Any CollegeMsg calibration on inspected periods is explicitly exploratory and cannot unlock claims of independently validated reliability. New data access requires provenance/rights approval; do not acquire it automatically.

### 4.3 Disagreement and abstention

Compare the same candidates using the frozen strongest structural baseline, temporal heuristic and eligible tabular model. Report rank/top-set agreement with the tie policy, not a variance over incomparable raw score scales. Probability dispersion is meaningful only between compatible probability models and remains a diagnostic.

Prespecify abstention reasons: unsupported task, unseen-node scope, insufficient positive outcomes, unavailable calibration, incompatible artifacts, missing causal assumptions, budget exhaustion and unstable action choice under the registered utility sensitivity analysis. Retain coverage/useful-answer rates so abstaining on everything cannot count as success.

## 5. Bayesian inference: one small, auditable model

Required first model: the rate at which a fixed method/configuration achieves a **prespecified practically useful outcome on independent synthetic graph instances**. Define success before running cases, for example exceeding a registered baseline by an AP difference of `delta`; freeze `delta` in the synthetic protocol, not after results.

For each fixed action/method `a`, assume `theta_a ~ Beta(alpha_a, beta_a)` and independent Bernoulli outcomes across graph instances under one declared generator distribution. With `s` successes and `f` failures, update to `Beta(alpha_a + s, beta_a + f)` exactly. Start with `Beta(1,1)` and sensitivity alternatives `Beta(0.5,0.5)` and `Beta(2,2)`. Register assumptions and priors before observing outcomes.

This models success across independent simulated instances, not the probability of a message on an individual edge, a graph-wide causal hypothesis, or universal algorithm superiority. Outcomes within a graph are not additional independent trials. Keep actions on independent simulated streams for the first analytic decision example; paired graph comparisons remain in the separate numerical evaluation and must not be fed into an independence likelihood without modelling that dependence.

Persist the hypothesis/action definition, generator identity, prior, likelihood, observation IDs and hashes, posterior parameters, credible interval and predictive distribution. Deduplicate observations so replay never updates twice. A model revision creates a new belief identity; old observations cannot silently be reinterpreted under a new success threshold.

Required checks: hand-computable updates, prior predictive simulations, posterior predictive checks for block success counts, prior sensitivity, and repeated synthetic calibration/coverage checks. Contradictory data, dependence or predictive misfit must trigger an explicit limitation/stop. Do not automatically multiply Bayes factors from overlapping experiments or treat “not significant” as evidence of no effect.

Broader Bayesian hypotheses need an explicit generative likelihood before support probabilities can be computed. An LLM cannot invent a posterior percentage from a collection of reports.

## 6. Decision theory: a bounded research controller

### 6.1 State, actions and utilities

Represent state as verified artifacts, admissible belief models, remaining resource limits, completed attempts and registered user objectives. Actions come from a small typed registry; include **stop and report** from the outset.

Initial actions may be: run one synthetic replicate of method A or B, inspect an available aggregate diagnostic, or stop and recommend a method **within the simulated benchmark**. These are research actions, not interventions on people or organizations. Unknown real-world preferences yield a request for a utility specification or a descriptive comparison; never guess social benefit from AP.

For the exact toy model, define terminal reward as success on one future independent simulated task (reward 1 for success, 0 otherwise) and a fixed experiment cost `c` in the same artificial utility units. Freeze the cost schedule, terminal decision, action eligibility and hard run limits. Monetary budget, wall time and memory remain separate non-negotiable constraints; converting time/cost into utility needs an explicit declared conversion.

This gives a meaningful, testable choice: another experiment is useful only if the expected improvement in the terminal choice exceeds its cost.

### 6.2 Compute expected value of sample information

For posterior state `D`, terminal method choice `d` and allowable next experiment `e`, compute:

`V_stop(D) = max_d E[U(d, theta) | D]`

`EVSI(e | D) = E_y[V_stop(D union {e,y}) | D] - V_stop(D)`

`net_value(e | D) = EVSI(e | D) - cost(e)`

The Beta–Bernoulli case permits exact enumeration over success/failure outcomes and posterior predictive probabilities. Select the feasible experiment with greatest positive net value; stop if none is positive. Use a deterministic tie rule. This is **one-step/myopic** value of information, not a globally optimal research policy. Impose at most ten experiment steps and recompute after each real registered observation.

Information gain (expected reduction in entropy) is an optional diagnostic or a separate policy baseline. It is not automatically useful decision value: an experiment can reveal much about an irrelevant parameter and still be a poor use of the budget. No weighted AP/entropy/cost score may be labelled EVSI without the corresponding utility and outcome model.

For real forecast workflows without a validated predictive model over experiment outcomes, the controller must report **VOI unavailable**. It may offer deterministic prerequisite/cost-based suggestions, clearly labelled heuristic. Do not transplant toy-model VOI numbers to CollegeMsg.

### 6.3 Verify the controller before granting autonomy

Compare exact myopic EVSI against stop immediately, a fixed experiment schedule, seeded random action choice and greedy posterior-mean selection under equal maximum budgets. Evaluate on independent simulated episodes: realized utility net of costs, terminal regret relative to the known simulator optimum, number of experiments, actual runtime, stopping behavior and failure rate. Ground truth stays evaluator-only; the controller observes sampled outcomes only.

Use paired episode seeds across policies for evaluation while preserving each policy's information boundary. Known-truth synthetic success validates the controller's mechanics under that simulator, not autonomous scientific discovery on public networks.

Required edge cases: an experiment with zero decision value, high entropy but irrelevant evidence, experiment cost exceeding its benefit, a decisive posterior, prior-sensitive recommendations, impossible actions, exhausted resources and repeated observations. Utility sensitivity may change the recommendation; show that rather than hiding it.

## 7. Causal inference: identification before estimation

Add a structured causal review contract with:

- Treatment/intervention, outcome, unit, time order, target population and estimand.
- A user-specified or explicitly hypothetical DAG, variable meanings and provenance.
- Confounding/selection assumptions, adjustment argument, consistency, positivity and measurement issues.
- Network interference: whether one unit's treatment changes another's outcome, and what exposure mapping or no-interference assumption is being made.
- Identification verdict: identified under stated assumptions, simulated intervention only, or not identified.

A DAG is an assumption artifact, not learned ground truth. A deterministic DAG checker can verify graph syntax/acyclicity and a registered backdoor criterion in its supported setting; it cannot verify that all confounders were measured. Unsupported identification problems must abstain. Do not condition on mediators/colliders by default.

For CollegeMsg, no explicit treatment, validated confounders or defensible intervention design has been established. Expected behavior is an informative **not identified** response. Correlation, centrality, forecasting accuracy and edge deletion do not identify causal influence. Existing edge-removal tools remain sensitivity/simulation tools.

Required demonstration is synthetic only: one independently generated graph-level outcome per unit, randomized binary treatment with known overlap, a measured confounder, and a linear structural outcome equation with known average treatment effect. State no cross-unit interference in this toy model. Compare naive association with one registered adjusted regression/g-computation estimator; verify known-truth recovery over repeated simulations. Include an unmeasured-confounding fixture where the system must refuse an identified causal claim.

Individual counterfactuals require structural equations and assumptions beyond an average treatment-effect estimate. Do not fabricate an individual's alternate outcome from fitted regression. Full network causal inference, causal discovery and observational CollegeMsg treatment effects are deferred.

## 8. Bayesian optimization: conditional, not mandatory

Small cheap grids are already transparent and adequate for many Sprint 6 methods. Bayesian optimization is warranted only if a remaining **expensive**, bounded continuous/discrete search has a clear objective and repeated evaluations provide a reason to use a surrogate.

Gate before implementation: specify the objective, permitted search space, noisy observation model, validation-only data, compute budget and comparison with random search. No changing task horizons, test splits, candidate universes or primary metrics inside the optimizer.

If justified after the required slice, one optional protocol may compare a Gaussian-process surrogate plus expected improvement with random search: 12 total evaluations each, including four initial points; identical domains and per-evaluation resource limits; failures counted; three independent synthetic episodes for plumbing only. Fit transformations/surrogates on observed validation objectives only. Do not claim optimizer superiority from three episodes. More evaluation requires a new frozen budget and independent evidence.

Expected improvement is an acquisition function for the registered optimization objective, not a universal research VOI calculation. The optimizer and experiment controller must not independently spend the same budget or tune against the same final test. No new package or cloud/GPU service is needed merely to complete this sprint. Skipping this branch is an expected successful outcome if the gate is unmet.

## 9. Architecture and product integration

Proposed modules/tools, not implemented interfaces:

| Component | Trusted responsibility | Agent boundary |
|---|---|---|
| `reliability_audit` | Validate partitions, calculate metrics/calibration/disagreement and interval eligibility | Aggregate evidence only; cannot move splits |
| `belief_update` | Apply one registered likelihood/prior to deduplicated observations | Cannot accept invented observations or arbitrary likelihood code |
| `experiment_decision` | Compute feasible actions, utilities and exact toy EVSI; include stop | Utility and resource changes require an explicitly versioned objective |
| `causal_identification_check` | Check supported DAG/estimand contracts and produce assumptions/refusal | No causal claim from a diagram alone |

Keep the existing process, SQLite records, typed tools, replay and artifact links. Do not add agent services or arbitrary Python execution. The LLM proposes; deterministic validators enforce. Evaluator keys, synthetic truth, future labels, local node IDs and raw events stay outside model context and tool permissions.

Belief state references evidence IDs, not natural-language confidence. Decision records include all candidate actions, rejection reasons, utility specification, assumptions, calculated EVSI where available, costs and stopping rationale. Every attempt, failure and refusal remains visible. Unknown billing or containment failure blocks further execution.

Extend the futuristic console with **Reliability**, **Beliefs**, and **Next experiment** sections inside the current investigation view. Distinguish score/probability, confidence/credible/sensitivity interval, and descriptive/predictive/simulated/identified causal evidence. Show “insufficient evidence” where appropriate. Provide a causal assumptions/refusal card rather than a decorative DAG implying causality. No opaque “AI confidence: 92%” badge.

The live model remains optional for orchestration/explanation. The full required loop must work in free mock mode, with replay. Existing allowance and authorization controls persist; do not assume remaining dollars from an earlier report are current or renew the allowance.

## 10. Protocol, staged delivery and budgets

Before implementation execution, freeze `protocols/sprint07_decisions_v1.md` with independent development/calibration/evaluation generator streams, complete seed lists, distribution assumptions, priors, success threshold, utilities, action budgets, metrics and stopping rules. Generate sealed evaluator instances only after the protocol is fixed; existing inspected cases are development evidence. Protect sealed truth through an actual trusted execution boundary, not merely a naming convention.

Suggested order:

| Session | Deliverable | Gate |
|---|---|---|
| 1 | Contracts, frozen protocol, tiny known-answer fixtures | Clear inferential target, split/observation ownership and utility units |
| 2 | Reliability diagnostics and interval eligibility | Independent numerical checks; two-window real-data CI refusal |
| 3 | Calibration workflow on synthetic temporal forecasts | Separate fit/assessment/test; no leakage or unsupported probability display |
| 4 | Beta–Bernoulli beliefs and exact one-step EVSI | Hand-computed updates/decisions, predictive checks and deduplication |
| 5 | Bounded controller and fixed-policy comparison | Same budgets, evaluator-only truth, preserved failures and correct stop behavior |
| 6 | Causal contract and toy demonstration | Known-truth checks and observational non-identification refusal |
| 7 | Agent/UI integration and clean replay | Traceable claims, no raw external data, reproducible end-to-end mock run |
| Optional | Bayesian optimization gate | Written justification; skip if not met |

Do one synthetic belief-update/next-experiment/stop cycle before broadening to calibration UI or causal examples. Sessions are work packages, not elapsed-time promises.

Proposed hard budgets to finalize before execution: CPU only; 30 minutes per registered comparison, 60 minutes total mandatory numerical workload; 120 seconds per tool invocation; 2 GiB maximum process memory where enforceable; 1,000 bootstrap resamples; ten autonomous steps per episode; no repeated attempts to obtain a desired result. Batching/checkpointing may preserve progress but cannot silently reset limits. Report unsupported OS isolation and fail expensive work safely rather than claiming a subprocess is a sandbox.

The independent-graph bootstrap uses at least 30 graphs. The decision-policy evaluation uses 100 independent simulated episodes, with cheap analytic updates, held separately from development cases. Calibration sample sizes, bin eligibility and synthetic distribution families must be set from the inferential target before execution. If their workloads exceed the cap, record an incomplete/blocked branch; do not shrink a frozen benchmark after inspecting scores. Paid spend defaults to USD 0; no cloud resources or dependency expansion is authorized by this file.

## 11. Acceptance checks and definition of done

- Verify formulas and interval labels against independent tiny examples. No CI for the existing two-window CollegeMsg result.
- Calibration partition and future-mutation tests; assessment labels inaccessible during calibrator fit, model selection and utility tuning.
- Paired graph-level resampling retains dependence within graphs. Invalid sample units and zero-positive cases produce explicit outcomes.
- Exact Bayesian updates/credible quantiles and posterior predictive probabilities match a separate reference implementation or numerical integration; prior/posterior predictive checks recorded.
- EVSI matches hand-enumerated examples, includes stop, respects utility units and cannot override hard limits. Entropy gain is not mislabelled expected utility.
- Causal fixtures include valid adjustment, a collider pitfall, positivity failure, hidden confounding and unsupported network interference. Refusals distinguish mathematical checks from unverified substantive assumptions.
- Claim checks reject invented probabilities, causal conclusions, ungrounded belief updates and confusion between interval types.
- Same-seed replay never double-counts observations or spends again. Cancellation, budget exhaustion and tampered artifacts preserve a sanitized failure record.
- Existing forecasting/community/structural regressions pass; clean offline reproduction records source/dependency/config hashes and all attempts. Tests count as passed only when executed.

Completion requires one usable mock research loop with honest reliability output, a registered Bayesian update, a computed next-action/stop decision, and a synthetic causal identification demonstration/refusal path. It does **not** require calibrated CollegeMsg probabilities, real-world causal effects, a GNN or Bayesian optimization.

Expected implementation artifacts: versioned contracts/protocols; trusted numerical modules and invariant tests; local belief/decision/reliability artifacts; UI integration; `docs/sprint07_guide.md`; `docs/sprint07_report.md`; minimized aggregate comparison results. The closeout must separate implemented capability, executed evidence, negative results, limitations and deferred branches.

## 12. Sources and interpretation

- [scikit-learn probability calibration](https://scikit-learn.org/stable/modules/calibration.html): calibration methodology and proper scoring diagnostics. A proper score measures more than calibration; it is not a standalone reliability guarantee.
- [Frazier, A Tutorial on Bayesian Optimization](https://arxiv.org/abs/1807.02811): motivation and acquisition-function framework for expensive optimization. The optional gate above is BLACKGRID's proposed engineering choice.
- [Hernán and Robins, Causal Inference: What If](https://miguelhernan.org/whatifbook): identification assumptions and the separation between associations and causal effects. The synthetic restriction and refusal policy above are project design decisions.

**Next smallest task after implementation authorization:** freeze a two-method Beta–Bernoulli synthetic decision example and verify, offline, a case where one extra experiment is worthwhile and a case where the correct action is to stop.
