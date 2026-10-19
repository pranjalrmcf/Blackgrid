# BLACKGRID: evidence-grounded network investigations

Technical summary | 19 October 2026 | [Two-page PDF](../output/pdf/blackgrid_technical_summary.pdf)

This brief preserves the v6 evaluation snapshot. The newer post-repair [v7 evaluation](current_system_eval_v7.md) is reported separately.

## 1. Thesis

An LLM can help choose a network analysis, but its fluency is not evidence that a scientific conclusion is correct. BLACKGRID explores a bounded alternative: use a model to propose registered analyses, execute trusted numerical tools, and accept factual claims only when they match saved evidence and its scope. The research question is whether statistical validation and criticism can reduce unsupported conclusions without eliminating useful answers. The present project demonstrates the machinery and measures its behavior; it does not yet establish a causal advantage over simpler research workflows.

## 2. Method and architecture

**Investigation workflow.** A local console or CLI accepts a question and validated configuration. Deterministic scope guards refuse unavailable targets; a real LLM can select an analysis family and allowlisted calls. A controller validates arguments, prerequisites and required analyses. Trusted tools execute under time and resource limits, then a family-specific critic checks factual values, evidence references and scientific scope. Validated community, structural and forecast answers use local evidence templates by default. A bounded model-writing path remains available for research reviews and controlled comparisons; it shares the same critics and spending controls.

**Durability and privacy.** LangGraph checkpoints and a SQLite operation ledger record progress, authorizations, reservations and receipts. Resume reuses verified completed work; an uncertain paid dispatch pauses rather than being resent automatically. Prices must be known before a paid request, and historical spending plus unresolved reservations count toward the configured ceiling. Raw events, node identifiers and pair rankings remain local; external model evidence is minimized to aggregates. These controls apply to trusted implementations, not arbitrary generated code in a hostile-code sandbox.

**Structural inference.** CollegeMsg events are validated against the recorded checksum and projected into a simple undirected graph for a fixed, size-selected window. Community modularity is compared with a degree-preserving rewiring null; the largest connected component is checked separately. A registered uniform edge-removal analysis tests sensitivity. Other tools calculate degree, normalized betweenness, descriptive community partitions, cross-community neighbour counts and ranking stability. These are structural measurements, not verified friendship labels or causal influence.

**Prediction and synthetic research.** Temporal forecasts use a fixed cutoff and horizon over the complete known-node candidate universe, with separate first-time and repeat-interaction tasks. Registered heuristics precede logistic models with temporal features; comparisons retain chronological information boundaries. Scores remain uncalibrated rankings. Separate synthetic studies demonstrate calibration diagnostics, Beta success-rate beliefs, exact one-step value-of-information decisions and causal identification gates. Research tools inspect these saved studies; they do not perform new real-world interventions.

<!-- PAGE BREAK -->

## 3. Measured results

| Evidence | Result | Interpretation |
|---|---|---|
| Current full regression [1] | 493 passed; zero failures, errors or skips; 266.64 s | Engineering and numerical checks, including offline instrumented providers; not an LLM capability score. |
| Most recent live system evaluation [2] | 23/24 strict passes (95.8%); 68.56 s; USD 0.00747418 | Earlier frozen snapshot: 17/18 supported questions and 6/6 deterministic refusals; not rerun after the final regression repairs. |
| CollegeMsg rolling development [3] | Repeat pairs: mean AP 0.2883; precision@100 0.408. New pairs: mean AP 0.00757; precision@100 0.044 | Five inspected windows, logistic_v2. About 40.8 repeat pairs versus 4.4 new pairs correct per top 100, averaged over windows. |
| Bitcoin OTC confirmation [4] | Logistic_v2 beat its registered reference in 5/5 evaluable windows for each task | Mean AP 0.04994 vs 0.02164 for new pairs; 0.17575 vs 0.03168 for repeat pairs. Dataset/task-specific predictive evidence. |

The live evaluation froze wording, expected targets, criteria, budget and stopping rules before execution. Four separate workers attempted every case once. Independent local checks verified artifact hashes, numerical evidence and forecast candidate membership; assistant semantic review checked responsiveness and scope. Six unsupported requests were refused by guards without model calls. All 18 supported requests used the real planner; four research cases also used model writing. The failure was a cross-community stability question answered as ordinary centrality stability. A later guard rejects that substitution, but no new live success rate is claimed. Full regression subsequently found and fixed an optional-secondary-result crash; all historical results remain separate.

## 4. Limitations and next experiment

**Evaluation scope.** The 24 questions are paraphrases across six familiar categories on reused evidence, not 24 independent graphs or an untouched generalization benchmark. Their reviewer was this assistant, not a human panel. Warm numerical caches contributed to latency. The headline live result predates the latest regression repairs, and UI rendering was outside that evaluation. A green regression suite cannot establish autonomous scientific discovery.

**Scientific scope.** CollegeMsg rolling windows were inspected during development. New-pair prediction is substantially harder than repeat interaction, and ranking scores are not calibrated probabilities. External confirmation on Bitcoin OTC does not establish universal transfer across networks. Missing edges are unknown, and uniform removal is one assumed observation mechanism. Synthetic calibration and causal examples do not establish real-data calibration or identified behavioral effects. In the saved 30-graph study, the sigmoid-minus-raw Brier bootstrap interval crossed zero; no probability-display gate was unlocked [5].

**Next experiment.** Freeze a matched-budget comparison of rule-based routing, real-model planning and validated summaries on independent graph instances and previously unseen question templates. Measure useful-answer rate, unsupported claims, abstention, failures, uncertainty and cost using independent numerical truth and a separate review rubric. Preserve all attempts and keep test outcomes out of tuning. This would test the thesis more directly than another paraphrase-only demonstration.

### Evidence references

1. [Current automated test status](current_test_status.md); full log and JUnit receipts remain local.
2. [Live evaluation v6 report](current_system_eval_v6.md), [frozen protocol](../protocols/current_system_eval_v6.json), [minimized summary](../results/current-system-eval-v6/summary.json).
3. [CollegeMsg rolling results](../results/sprint06-v2/summary.json); development evidence.
4. [Bitcoin OTC confirmation](../results/sprint06-v3-bitcoin/summary.json), [protocol](../protocols/sprint06_prediction_v3_bitcoin.md).
5. [Synthetic study report](sprint07_report.md), [minimized results](../results/sprint07-v1/summary.json).

Original project code and documentation are MIT-licensed. Dataset, dependency and third-party asset terms remain separate; raw datasets are not redistributed.
