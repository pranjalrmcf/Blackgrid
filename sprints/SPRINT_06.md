# BLACKGRID — Sprint 6: baseline-first temporal link prediction

**Planning date:** 18 October 2026.<br>
**Status:** proposed implementation plan; no Sprint 6 code, training or experiments executed.<br>
**Authorization:** this request authorizes this document only. Implementation, new dependencies, paid calls and data processing are not authorized by this plan. Existing paid allowances must not be reset or enlarged.

## 1. Decision and intended outcome

Add one useful predictive capability to the existing research system: rank pairs of observed nodes by their likelihood of an observed interaction in a specified future interval, using only information available at the forecast cutoff.

Traditional link prediction is the foundation. Temporal information is an additional source of evidence, not a reason to start with a temporal GNN. Compare simple topology scores, temporal heuristics and one small supervised model under a frozen protocol. GNNs are an optional later escalation, not a Sprint 6 completion requirement. A strong heuristic winning is a successful result.

Target question:

> “Which previously unconnected pairs are most likely to exchange a message in the next forecast window, and does using recent activity improve the ranking?”

The system should state the cutoff, horizon, eligible nodes, candidate pairs, selected method, validation evidence, withheld-test performance when available, and limitations. Scores are rankings unless calibration has been separately demonstrated. Individual pair tables remain local.

The broader Sprint 5 agent/critic evaluation is deferred at the user's request. Sprint 6 correctness checks and predictive evaluation remain necessary. Finishing implementation does not establish forecasting skill, agent superiority or generalization beyond this dataset.

## 2. Starting point and boundaries

Reuse Sprint 5's local console, seven-tool registry, durable workflow, artifact store, mock/replay modes, critic and paid budget controls. See [Sprint 5](SPRINT_05.md), [live implementation report](../docs/sprint05_live_report.md), and [decision log](../docs/decision_log.md).

CollegeMsg retains directed timestamps and repeated events in the raw source, whereas existing community/centrality tools operate on an undirected simple projection. A static full-dataset graph is not an acceptable input for a historical forecast: it contains future information. Prediction needs a separate, cutoff-specific event pipeline and artifact identity.

Keep these outside this sprint: employee data, influence claims, causal prediction, continuous-time event intensity models, next-event timestamp prediction, recommendations delivered to people, graph databases, GPU provisioning, automated architecture searches and new agent services.

### Data authorization gate

Decision D-003 explicitly accepted local non-commercial CollegeMsg analysis for Sprint 1 only; that is not a verified open license. Before executing Sprint 6 real-data forecasting, record an updated rights/use decision for this scope. Unresolved terms block the CollegeMsg experiment, not synthetic development. Do not redistribute raw or pair-level derived data. Preserve both source citations and the original file hash. No new dataset acquisition is needed.

## 3. Define two different forecasting tasks

Start with undirected pair-level observations to match the current system and keep the first implementation narrow. An event in either direction counts as a pair interaction. Explicitly disclose that sender/recipient roles are discarded. Preserve direction and timestamps in the underlying event records for a later directed extension.

For cutoff `t` and horizon `H`, history is strictly before `t`; labels use `[t, t + H)`. Nodes are eligible only if observed in history. No future-derived node list, community partition, degree, embedding, normalization or candidate filter is permitted.

| Task | Eligible pairs at cutoff | Positive label | Interpretation |
|---|---|---|---|
| **New-pair forecasting — primary** | Distinct historical nodes with no observed interaction with each other before `t` | At least one observed interaction during the horizon | First observed connection between known nodes |
| **Repeat-interaction forecasting — secondary** | Distinct historical nodes that have interacted before `t` | At least one observed interaction during the horizon | Whether a previously observed pair interacts again |

No message in the horizon means **no observed interaction during that horizon**, not proof that the pair has no relationship. Pairs with future events beyond the horizon remain valid zero labels for this horizon; never filter them using future knowledge. Multiple events yield one binary label, while historical multiplicity supplies frequency features. Exclude self-pairs and report exclusions.

Novel nodes are out of scope for this transductive known-node task. Report the number/fraction of future positive pairs excluded because at least one endpoint was unseen. Do not silently drop cold-start cases and claim complete network coverage.

Static randomly masked link reconstruction may be used on tiny synthetic fixtures to verify formulas. It is a different task, not evidence of future forecasting skill, and is not a parallel CollegeMsg benchmark this sprint.

## 4. Freeze the temporal protocol before results

Create `protocols/sprint06_prediction_v1.md` before running a real-data comparison. Register question, tasks, candidate rules, data hash, time boundaries, features, grids, seeds, metrics, limits, selection rule and stopping criteria. Record whether any test data/results have previously been inspected.

Proposed first protocol, fixed by elapsed time rather than row counts:

1. Let `t0` be the minimum validated event timestamp and `t_end` one second after the maximum. Let `D = t_end - t0`. Fix `H = D / 10`, with integer boundaries `b_i = t0 + floor(i * D / 10)` and `b_10 = t_end`. Record actual boundaries; event ties never straddle a cutoff.
2. Build supervised development examples at cutoffs `b_2`, `b_3`, `b_4`, `b_5`, with next-bin labels. Each feature snapshot uses only its own past. These labels all finish by `b_6`.
3. Use cutoffs `b_6` and `b_7` for validation. Select models/hyperparameters on the mean primary validation metric, never the test interval.
4. Use cutoffs `b_8` and `b_9` as the sealed final test, each predicting the next bin. Freeze one method/configuration per task before opening test results.
5. Use fixed-origin batch forecasting within each horizon: do not update features from events inside that horizon. At `b_9`, observations from the preceding bin are legitimately historical; refresh features and candidate sets, but do not retrain, retune or inspect `b_8` scores before both test predictions have been saved.
6. After selection, the supervised model may be refitted once on all labelled development and validation examples ending by `b_8`. Keep its selected preprocessing/configuration fixed. Both final forecasts use those frozen learned parameters.

Freeze the partition before feature exploration. If timestamps or label counts make the task unsuitable, report that fact and stop rather than moving cutoffs until results improve. Horizon comparisons and alternate observation windows require a versioned exploratory protocol and cannot replace this primary result.

The LLM receives aggregate development/validation evidence only. Evaluator-held test labels and metrics must be inaccessible to its tool credentials and planning state. Numerical test evaluation occurs only after prediction artifacts are frozen; final reporting may receive the resulting aggregate metrics, with no remaining tuning actions. A directory name alone is not access control: use a trusted evaluator boundary; where isolation is unavailable, keep test evaluation outside the agent workflow.

## 5. Candidate universe and fair scoring

For each task/cutoff, use exactly the same eligible pairs, labels and tie rule for every method. Canonicalize undirected endpoints so reversals cannot enter different partitions. Keep timestamp-tied events together, preserve repeated events, and flag exact duplicate records without silently changing the dataset.

Prefer the **complete eligible candidate universe** for this small dataset. Stream feature/scoring batches instead of constructing a dense adjacency matrix. Proposed hard caps per task/cutoff: 2 million candidates and 2 million labelled training examples across its development snapshots. Check sizes from history before running methods. If a cap is exceeded, stop with a recorded capacity outcome. Do not silently switch to sampled evaluation or change node eligibility. A sampled protocol would need its own version, prevalence statement and weighting rules.

Do not use balanced random negatives as the headline result. They can make the task substantially easier and alter average precision. The two task strata already separate old-pair persistence from genuinely new observed pairs. For new-pair forecasting, also report performance/coverage on candidates with and without a historical two-hop path; this is a diagnostic on the same frozen predictions, not a new candidate definition.

Use a deterministic seeded tie-breaking hash of canonical local pair IDs, independent of labels and shared across methods. Disclose tie rates. Never use future events to select supposedly harder zero-label examples.

## 6. Baseline ladder and restricted tuning

All formulas, training rows and temporal aggregations must be specified and unit-tested before comparison. Features use historical observations only. Zero-degree, disconnected and zero-denominator behavior is explicit.

| Stage | Methods | Purpose / budget |
|---|---|---|
| 0. Sanity controls | Seeded random ranking; constant score | Catch broken labels, metrics and tie handling |
| 1. Structural heuristics | Common Neighbors; Jaccard; Adamic–Adar; Resource Allocation; Preferential Attachment | Strong, cheap traditional references; one configuration each |
| 2. Temporal heuristics | Recent endpoint activity product; recent-window Resource Allocation; pair frequency and pair recency for repeat interactions | Test whether time adds useful information; never pretend unseen pairs have prior frequency |
| 3. Small supervised baseline | Regularized logistic regression over the same historical structural and temporal features | Test feature combinations before graph representation learning |
| 4. Optional escalation | One bounded non-GNN addition, or a separately justified GNN investigation | Not required for Sprint 6; no model added merely because the others do not win |

Definitions to freeze:

- Structural scores use the cumulative simple graph before the cutoff. Record the standard undirected formulas and logarithm convention for Adamic–Adar; define zero scores for empty denominators.
- Recent methods use historical windows of `H` and `2H` only; two configurations per applicable method. Activity counts historical events incident on an endpoint. Pair recency uses time since the last historical pair event, with a fixed monotone score; pair frequency counts historical pair events. These two pair-specific methods apply to repeat interactions only.
- Logistic features: five structural scores, endpoint cumulative degree and recent event activity (symmetric sum/product), plus historical pair count/recency in the repeat task. No node identity feature. Fit missing-value handling/scaling on supervised development rows only during selection. Use `log1p` for nonnegative counts, an explicit unseen-recency indicator where applicable, and no feature selection after test inspection.
- Fit one logistic model per task with three fixed regularization strengths (`C = 0.1, 1, 10`), fixed `H` activity window, no class reweighting and no automatic threshold search. Cap iterations at 200; nonconvergence is a failed configuration, not permission to extend the search. Prefer the simplest tied candidate.

For each task, select the strongest non-temporal baseline and the strongest temporal method on validation. Freeze both for final paired comparison; also report the full prespecified baseline table. The main question is temporal improvement over the selected static reference, not whether a complex method can beat a random control.

### GNN gate: last resort, separate decision

Do not add PyTorch/PyG/DGL or train a GNN in the required Sprint 6 path. First establish all of the following using development/validation evidence only:

1. The split, candidate policy and metrics pass independent checks, with adequate positive examples and within-budget runtime.
2. Traditional and temporal baselines and the small supervised model have received their full documented budgets.
3. A specific remaining failure suggests learned neighborhood representations could help; “GNNs are more advanced” is not a reason.
4. A written proposal specifies one architecture, a fair comparator, a small bounded search, training/inference cost and a practical improvement target before training.

If approved later, use one simple architecture and decoder first, at most three configurations and three seeds each, with no architecture sweep. Historical topology only; embeddings must be recomputed at allowed cutoffs. A static GNN trained on chronological snapshots must be described as such, not as a continuous-time temporal model. New dependencies or paid compute need implementation authorization. If the original test results have already been opened, use a new untouched benchmark for any superiority claim; the old test is development evidence. Failure to outperform the heuristic within the cap ends the branch.

## 7. Metrics, comparisons and honest interpretation

Primary selection/test metric: **average precision (AP)** over the complete eligible universe, separately for each task and cutoff. Record positive count, candidate count and prevalence alongside it. AP is not interchangeable with trapezoidal PR-AUC.

Secondary metrics: Precision@100 and Recall@100, with `K = min(100, candidate_count)`; ROC-AUC as a supplementary measure only. Report zero-positive cutoffs as not evaluable for AP/recall comparisons, not perfect or silently omitted. A task needs both validation cutoffs evaluable to select a winner; otherwise mark insufficient evidence and version a future protocol rather than retuning this one.

Report each temporal window, arithmetic means, absolute paired differences and costs. Two adjacent held-out windows from one network do not provide a credible broad confidence interval. Do not bootstrap individual pairs as independent samples. No statistical significance or cross-network generalization claim from this small experiment. Multiple prespecified methods are disclosed; validation selection and final test roles stay separate.

Logistic outputs may be displayed as **uncalibrated model scores**. The UI must not show “80% chance” without a separate held-out calibration protocol and evidence. Calibration, directed forecasting, additional horizons and larger independent temporal benchmarks are follow-on work.

## 8. Integrate prediction into the agent and console

Proposed registered tools, not implemented commands:

| Tool | Responsibility | Access boundary |
|---|---|---|
| `temporal_profile` | Validate event schema, coverage and cutoff-specific history statistics | Aggregate summaries to planner; no raw events externally |
| `link_prediction` | Apply a registered heuristic or frozen fitted model to a validated task/snapshot | Local scored-pair artifacts; aggregate method/scope metadata externally |
| `prediction_compare` | Compare compatible development/validation artifacts and frozen metrics | No agent access to sealed test labels; final test evaluation stays trusted |

Keep temporal split construction and test evaluation in trusted deterministic orchestration rather than discretionary LLM tools. The planner may select a supported task/method and explain it, but cannot move cutoffs, create arbitrary candidates, request test feedback for tuning, execute generated code or increase budgets. A prediction result cannot be validated by the community-significance critic rules.

Extend typed contracts and the claim checker for predictive association: every claim names task, cutoff, horizon, candidate policy, metric, split, method and artifact reference. Reject unsupported probability, causal or influence language, incorrect comparisons and claims about unseen nodes.

Preserve the futuristic console. Add a clear **Forecast connections** path, with task selector (**new connections** / **repeat interactions**), history cutoff, forecast horizon, local ranked pairs, aggregate validation/test results, model comparison, runtime and cost. Separate retrospective held-out evaluation from a prospective forecast, which has no realized future labels yet. Reuse the existing answer/evidence/activity/cost views. Scope selectors must not silently reuse Sprint 5's full-graph projection for prediction.

The free mock path runs actual deterministic scoring with scripted decisions. Real AI is optional for planning/explanation and stays under the existing allowance; training and ranking require no LLM calls. Raw IDs, events, pair rankings and evaluator labels never enter external prompts or traces. Free-text questions containing identifiers require local rejection/redaction before external submission.

## 9. Sessions and acceptance gates

| Session | Deliverable | Acceptance gate |
|---|---|---|
| 1. Protocol and contracts | Task/split/candidate definitions, rights decision, frozen budgets, synthetic fixtures | No feature or candidate source can access future data; unresolved rights block real data only |
| 2. Temporal pipeline | Cutoff-specific history, pair labels, immutable manifests | Boundary/tie/repeat/reverse-edge/cold-start checks pass; changing future events cannot change historical features |
| 3. Traditional baselines | Five heuristics, random controls, streaming candidates | Known-answer graphs and independent reference calculations match; same candidates/ties for all methods |
| 4. Temporal + tabular | Recency/activity baselines, bounded logistic model | Training-only transforms, fixed grids and validation-only selection; fit failures preserved |
| 5. Predictive evaluation | Trusted evaluator, sealed artifacts, paired comparison report | Test predictions frozen before metrics; all attempts/costs retained; no false probability or generalization claims |
| 6. Product integration | Registered tools, claim validation, console forecast flow | Correct task routing, evidence links, no raw external IDs, mock/replay and cancellation work |
| 7. Reproduction and closeout | Source/config snapshot, clean offline reproduction, guide/report | End-to-end synthetic workflow reproduces; real-data outcome reported only if authorized and executed |

Complete one synthetic new-pair forecast end to end before adding repeat interactions or UI breadth. These are ordered work sessions, not a promise of calendar duration. Stop at a failed gate and record the reason.

### Resource and stopping rules

Proposed CPU-only local budget, to freeze before execution:

- Per task/cutoff/method configuration: 120 seconds and a 1 GiB planned working set; stream in batches of at most 50,000 candidates.
- Whole Sprint 6 real-data baseline comparison: 60 minutes wall time, at most 30 fitted model configurations total, maximum 2 GiB process memory.
- Reuse cached historical features only with data/cutoff/schema/config hashes. Record actual CPU, memory, wall time and source revision.
- Enforce wall time and memory using available OS controls; if unavailable, do not claim a subprocess is a sandbox or a hard memory cap. Preflight capacity and trusted-code-only restrictions remain required; unsupported containment yields a clear failure before expensive work.
- Stop on exhaustion, leakage, malformed data, unavailable rights, unknown pricing or attempted test-key access. Do not silently reduce candidates, skip failed methods or extend limits. No cloud spend or new paid evaluation is included.

## 10. Required correctness and failure checks

- Tiny triangle, path, star and disconnected graphs with independently computed heuristic scores; symmetric pair canonicalization and zero denominators.
- Timestamp boundary events, tied times, self-loops, repeat events, future-born nodes, future-positive pairs outside the current horizon, and both candidate task definitions.
- A future-event mutation check: alter events at/after a cutoff and prove history features, node eligibility and candidates are unchanged; current-horizon labels may change, as expected.
- Supervised snapshot labels finish before the validation/test boundary; held-out edges never enter message passing, embeddings, recent counts or preprocessing fits.
- Independent hand-calculated AP/Precision@K/Recall@K examples, ties, empty candidates, no positives and no usable negatives.
- Immutable candidate hashes shared across methods; deterministic seed/config replay; malformed schemas and incompatible artifact comparisons rejected.
- Planner attempts to inspect test labels, move cutoffs or emit arbitrary code rejected; paid budget and cancellation failures produce preserved sanitized records.
- One clean offline end-to-end reproduction, plus current community/centrality regression checks so Sprint 6 does not break Sprint 5.

## 11. Definition of done and deliverables

Sprint 6 capability is complete when an authorized user can run a reproducible known-node forecast with deterministic baselines, compare static and temporal methods under the frozen protocol, and inspect evidence in the existing UI. Predictive skill may be weak or absent; that must remain a valid result.

Expected implementation artifacts:

- Versioned prediction contracts, protocol, temporal data/split/candidate manifests and rights record.
- Numerical scoring tools, bounded tabular training, trusted evaluator and focused invariant checks.
- Forecast UI, predictive claim checks and a mock/replay workflow.
- Local prediction artifacts and selected-model metadata; reviewed aggregate results only in shareable reports.
- `docs/sprint06_guide.md` and `docs/sprint06_report.md`, separating implemented capability, executed evidence, failed attempts, deferred work and limitations.

Do not mark the CollegeMsg forecast validated if only synthetic tests ran. Do not mark agent benefit established because numerical baselines run correctly. A skipped GNN is an explicit expected outcome, not unfinished Sprint 6 work.

## 12. Research references informing the plan

- [SNAP CollegeMsg documentation](https://snap.stanford.edu/data/CollegeMsg.html): source semantics and temporal event format. The source page does not by itself establish redistribution permission.
- [Poursafaei et al., Towards Better Evaluation for Dynamic Link Prediction (2022)](https://arxiv.org/abs/2207.10128): motivates careful temporal evaluation and scrutiny of negative sampling. This plan uses its own explicitly defined fixed-horizon pair task; it does not claim benchmark equivalence.
- [Huang et al., Temporal Graph Benchmark (2023)](https://proceedings.neurips.cc/paper_files/paper/2023/hash/066b98e63313162f6562b35962671288-Abstract.html): motivates realistic temporal comparison and reproducible evaluation. No universal claim that GNNs win or lose follows; BLACKGRID must measure its own task under equal rules.

**Next smallest action, after implementation authorization:** freeze the prediction contract and build a tiny synthetic temporal fixture that demonstrates one future-edge leakage rejection and one correct new-pair ranking, entirely offline.
