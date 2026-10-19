# BLACKGRID — Future potential and roadmap to completion

**Planning snapshot: 18 October 2026.** This document describes the intended product,
future research questions, remaining work and completion gates. It does not authorize
implementation, experiments, paid model calls, new datasets, publication or infrastructure.
No code was changed to create it.

## 1. The goal in plain English

BLACKGRID aims to become a bounded network-science research assistant. A user asks a
question about a network; the system constructs a justified investigation, runs approved
calculations, checks alternative explanations and uncertainty, and produces an answer
whose factual claims link to saved evidence.

The intended workflow is:

**Question → research plan → validated experiment → numerical tools → evidence checks
→ critic → reproducible report, qualified conclusion or abstention.**

The AI roles propose actions and explain findings. Registered numerical tools perform
the calculations. The controller enforces permissions, budgets and stopping rules.

The long-term ambition includes agentic research, graph machine learning, Bayesian
uncertainty, causal reasoning and efficient model operations. Adding those technologies
is not itself success: each addition must make a defined investigation more useful or
reliable than a simpler alternative.

## 2. Why the system could be useful

Individual network metrics and community algorithms are already available in libraries.
BLACKGRID's intended value is coordinating the work needed to turn their outputs into a
defensible answer: choosing a suitable method, checking prerequisites, comparing with
baselines, testing assumptions, recording failures and explaining the limits.

For example, a high community score can have several explanations: group structure,
uneven node degrees, disconnected components or incomplete observation. A useful
research assistant investigates those possibilities rather than reporting the score alone.

Potential users include network researchers, analysts studying approved communication
or collaboration data, and teams investigating appropriately licensed infrastructure or
information-flow networks. These are possible applications, not validated customers or
demonstrated real-world impact.

## 3. What exists today

The implemented foundation includes:

- CollegeMsg parsing, checksum verification and descriptive full-file ingestion.
- A historical community-versus-null experiment on a fixed first-week projection.
- A separately versioned full-dataset CollegeMsg experiment implementation and config.
- Network summaries, degree-preserving randomizations and edge-removal sensitivity.
- Planner, analyst and reviser roles, plan validation and a rule-based claim critic.
- A resumable LangGraph workflow with durable operations, budget tracking, authorization
  gates, receipts, cancellation paths and a local interactive console.
- Evidence-linked reports, run manifests, mock execution, a live-provider adapter and replay.
- Synthetic fixtures, fresh-instance validation, independent artifact scoring, a real
  CPU Louvain–Leiden comparison and a blinded human-review export.

The current scientific scope is still narrow. Most comparative evaluation uses a fixed
mock provider. A working live path is not evidence that criticism improves real models.
Broad temporal reasoning, leakage-safe prediction, calibrated probabilistic models and
identified causal estimation remain future capabilities.

### Keep the data scopes distinct

| Scope | Meaning | Existing reference |
|---|---|---|
| Full-file ingestion | Validate and describe every recorded message; save aggregate statistics | [Ingestion guide](FULL_DATA_INGESTION.md) |
| Historical first-week experiment | Analyze the fixed small projection under its original protocol | [Sprint 1 experiment](../protocols/sprint01_experiment.md) |
| Full-dataset experiment | Analyze the pooled recording period under separate exploratory limits | [Full-dataset protocol](../protocols/full_dataset_experiment.md), [configuration](../configs/collegemsg_full.json) |
| Sprint 3 evaluation | Compare workflow conditions and community methods on synthetic networks | [Sprint 3 report](sprint03_report.md) |

The full-dataset implementation is present in the working tree at this planning snapshot.
This documentation task did not execute or independently verify its latest results.
Pooling the entire recording period into one static graph is also different from
analyzing how the network changes over time.

The Sprint 3 report records 8 unsupported claims among 36 validated-condition claims,
despite 20 of 24 answers meeting its strict usefulness gate. Both conditions recovered
four evidence-supported positive verdicts, but neither supplied a fully supported useful
positive answer on those four tasks. Those scripted findings expose remaining weaknesses;
they do not establish the main research thesis. The report's 209 passing tests are a
historical verification record, not a claim that tests were rerun for this document.

## 4. Questions an advanced BLACKGRID could investigate

These are intended capabilities. Each needs the corresponding tools, data contract and
evaluation before the system can claim to answer it reliably.

| Area | Example questions | What must be added or established |
|---|---|---|
| Network structure | Which groups exist? Which connections bridge otherwise separate groups? Is a pattern unusual under a suitable null? | A broader validated tool registry, suitable null models and uncertainty about method choices |
| Temporal change | When do groups form, merge or split? Did fragmentation increase during a specified period? | Event-time graph construction, fixed windows and validated change-detection methods |
| Prediction | Which observed-unconnected pairs will connect next? Which groups may split? | Time-respecting evaluation, candidate definitions and tuned simple baselines |
| Information spread | Where could information travel? Which structures create bottlenecks? | Explicit flow or diffusion models; actual transmission data for empirical validation |
| Resilience | How does a network respond to random failures or specified disruptions? | Validated perturbation experiments and a defined measure of network function |
| Missing observations | Could gaps explain apparent fragmentation? Which conclusions survive biased missingness? | Degree-, group- and time-dependent missingness scenarios, with assumption sensitivity |
| Uncertainty | How reliable is a forecast? Which conclusion depends strongly on the model or prior? | Valid probabilistic models, predictive checks and calibration evidence |
| Simulated interventions | Under a specified simulator, what happens if connections are added or removed? | A documented simulator, intervention definition and known-answer checks |
| Identified causal effects | What effect does an intervention have under a justified identification strategy? | An estimand, suitable data, interference analysis, identification and sensitivity checks |
| Scientific reliability | Does the result reproduce? Does criticism improve conclusions under equal budgets? | Independent evaluation, held-out cases, human review and controlled ablations |
| Efficient research | Can a cheaper model or simpler method achieve comparable quality? | Frozen quality targets, routing experiments and joint quality/cost/latency measurement |

### Questions about influence require care

An advanced system should distinguish structural centrality, reach under a diffusion
model, predictive association and actual causal influence. They are different quantities.
A node with many connections is not automatically persuasive, trusted or causally important.
Real influence claims need appropriate observations and, for causal claims, identification.

### Examples of a complete investigation

> “This network appears to have become more fragmented. Verify the change, check whether
> changes in observation could explain it, compare plausible alternatives, and report
> what is still uncertain.”

> “Compare link-prediction methods using only information available before the prediction
> cutoff. Report ranking performance, uncertainty, computational cost and failure cases.”

> “Under this explicit failure model, compare two network designs. Explain whether the
> conclusion survives a different failure mechanism.”

These require several coordinated steps. A successful investigation may end with a
limited answer or a refusal when the available evidence cannot identify the requested fact.

## 5. What “complete” should mean

An unrestricted system capable of answering every network-science question has no useful
finite completion criterion. BLACKGRID needs a declared supported scope and release gates.

**A practical research-assistant release** should support a small set of real questions
reliably, with tested tools, reproducible evidence, a usable local workflow and measured
behavior on independent cases. It should explicitly identify unsupported requests.

**The broader research platform** adds validated temporal analysis, prediction,
probabilistic uncertainty, simulated and identified causal investigations, and efficient
bounded experiment selection. These extensions should have separate acceptance criteria;
they need not all ship in the first useful release.

**A research contribution** requires evidence for a specific novel claim. For BLACKGRID,
the primary question remains whether statistical validation and uncertainty-aware criticism
reduce unsupported conclusions while preserving useful discoveries under comparable budgets.
A functional application, many passing tests or a favorable demo cannot answer that alone.

## 6. Ordered roadmap and completion gates

The stages below are a proposed dependency order, not committed sprint numbers or dates.
Reliability, privacy and reproducibility apply throughout. A later stage proceeds only
when its prerequisites are satisfied; a negative finding can justify stopping or simplifying.

### Stage A — Close current reliability gaps

**Work required**

1. Review the 81 blinded Sprint 3 claims using a documented human rubric and record
   disagreements with the automated evaluator. Where feasible, use a second reviewer.
2. Define or remove vague strength language; require the exact evidence needed for
   numerical comparisons, including both sides of a comparison.
3. Design critic and evaluator revisions using development evidence, then freeze new
   validation cases before measuring improvement. Do not relabel inspected cases as fresh.
4. Correct prompt/specification mismatches, including sensitivity-replicate descriptions.
5. Address the documented suite-level manual-interruption status limitation, retaining
   failed attempts and distinguishing cancellation from work that is still running.
6. Check current full-scope changes against historical-window isolation, configuration
   validation, reports, privacy and reproducibility. Align status documentation with evidence.
7. Complete outstanding recovery checks before claiming the relevant live behavior is verified.

**Gate:** Fresh-case evaluation shows that the targeted defects are handled, numerical
oracles agree, claims resolve to verified evidence, and interrupted or failed work has
an understandable final record. Existing historical runs remain intact.

### Stage B — Establish real-model scientific reliability

**Work required**

1. Freeze a small live pilot protocol, task mix, model versions, prompts, evaluator,
   budgets, retry limits and stopping rules. Obtain explicit paid-execution authorization.
2. Compare the deterministic rule baseline, tool-only agent and validated agent under
   comparable budgets. Add validator/critic/uncertainty ablations as those components exist.
3. Measure unsupported claims, useful discoveries, completion, abstention, omissions,
   failures, latency and cost. Report denominators and performance by task family.
4. Use pilot variability to select the confirmatory sample size and prespecify the minimum
   useful improvement and acceptable loss of discovery recall before fresh test execution.
5. Use independent graph units, paired comparisons and an appropriate multiple-testing
   and optional-stopping policy. Keep sealed answers inaccessible to agent roles.
6. Freeze the final procedure before a separate held-out evaluation. Report null results.

**Gate:** A reproducible, independently assessed comparison establishes what improves,
what deteriorates and at what cost. If the critic does not help, simplify or redesign it;
do not declare success by selecting favorable examples.

### Stage C — Expand descriptive and temporal investigations

**Work required**

1. Add versioned contracts for directed, weighted and temporal networks, preserving the
   raw events and the meaning of each edge. Keep proxy and observed links distinct.
2. Register focused tools for bridging structure, robustness and changes over time, with
   numerical oracles and explicit method prerequisites.
3. Prespecify windows, time comparisons, metrics and change-detection thresholds;
   distinguish change in the network from change in its observation process.
4. Evaluate multiple justified community methods or resolutions without choosing whichever
   produces the most attractive significance result.
5. Validate full-period and temporal analyses separately from the historical first-week
   experiment. Preserve their different scopes, limits and conclusions.

**Gate:** Tiny known-answer temporal examples and fresh synthetic cases demonstrate
correct ordering, construction and failure behavior; approved real-data findings remain
exploratory unless a separate confirmatory design supports more.

### Stage D — Add graph prediction, then justify graph ML

**Work required**

1. Define the prediction target, observation horizon, available information, candidate
   universe and treatment of censored or unobserved pairs.
2. Use chronological training, validation and test splits. Compute features, topology,
   embeddings and preprocessing only from information allowed at each cutoff.
3. Keep duplicate and reverse representations of a target together. Define node overlap,
   cold-start behavior and transductive versus inductive scope.
4. Start with suitable simple heuristics and a simple learned baseline. Tune on validation
   under documented budgets before considering one embedding method or GNN.
5. Report PR-AUC and ranking metrics under the actual candidate protocol, with prevalence,
   meaningful negative-sampling assumptions, uncertainty, runtime and memory.
6. Add a GNN only if the workload and comparison justify it; retain negative results.

**Gate:** An independently checked leakage-safe benchmark demonstrates whether the more
complex model adds useful predictive value. A sophisticated architecture is optional;
honest performance against strong simple baselines is required.

### Stage E — Make uncertainty useful and testable

**Work required**

1. Extend uniform edge-removal checks to plausible degree-, group- and time-dependent
   missingness, including biased observation scenarios.
2. Separate observation, graph-construction, sampling, parameter and model uncertainty.
3. Introduce one explicit probabilistic model only where it answers a defined question.
   Record priors, assumptions, inference diagnostics and computational limits.
4. Perform prior and posterior predictive checks. Evaluate interval coverage on repeated
   synthetic truth and probability calibration using proper scores and reliability checks.
5. Test whether uncertainty-aware criticism improves decision quality or appropriate
   abstention, rather than merely making explanations sound cautious.

**Gate:** Uncertainty estimates have demonstrated adequacy for their declared setting.
Confidence intervals, Bayesian credible intervals and assumption-sensitivity ranges are
named correctly. Model scores are not called calibrated probabilities without evidence.

### Stage F — Add intervention reasoning with causal gates

**Work required**

1. Begin with explicit synthetic structural models and known interventions.
2. Define treatment, outcome, unit, time ordering, estimand and the assumed causal structure.
3. Address interference or spillovers, confounding, selection, measurement and positivity.
4. Separate simulator conclusions from identified real-data effects. For observational
   data, require an identification argument and sensitivity to unmeasured confounding.
5. Evaluate refusal on non-identifiable cases as carefully as estimation on identifiable
   ones. Correlation, causal discovery and an LLM-generated graph are insufficient alone.

**Gate:** The system estimates only what the assumptions and design identify and
reliably abstains otherwise. It does not recommend interventions affecting people
from exploratory structural patterns.

### Stage G — Support bounded adaptive research

**Work required**

1. Allow the planner to select among an expanded, typed and allowlisted experiment registry.
2. Register hypotheses, alternatives, metrics, selection budgets and stopping policies
   before confirmatory work. Keep exploratory proposals explicitly separate.
3. Preserve every attempted hypothesis and failed tool call. Account for adaptive selection
   and multiple testing rather than retrying experiments until a favorable result appears.
4. Test multi-step investigations, method-prerequisite failures and answer-key access attempts.
   Keep numerical checks and evaluator truth independent of planner and critic roles.
5. Require approval for new spending, external disclosure or actions beyond an existing
   authorization scope; do not grant arbitrary generated-code execution.

**Gate:** Additional autonomy increases useful validated investigations without an
unacceptable rise in unsupported claims, leakage, resource use or unrecorded failures.

### Stage H — Improve efficiency and operational readiness

**Work required**

1. Measure quality, cost, latency distributions and failure rate on a fixed workload.
2. Evaluate model routing and data/model/config-bound caching with explicit quality targets;
   distinguish cold and warm cache performance and actual from maximum permitted spend.
3. Consider batching, quantization or local serving only after a measured bottleneck
   justifies the added implementation and hardware requirements.
4. Strengthen isolation where needed: enforced CPU, memory, output and wall-time limits,
   isolated files, denied worker network access and read-only inputs. Until then, continue
   to restrict execution to trusted tools and disclose the containment boundary.
5. Add quality regressions, dependency/license review, release rollback and tested recovery.
   Improve the existing local interface where users need help understanding evidence.

**Gate:** Efficiency gains preserve a prespecified quality floor; recovery and limits are
demonstrated under failure tests. No graph database, distributed services, Kubernetes,
dashboard rewrite or custom model hosting is required without workload evidence.

### Stage I — Package and independently reproduce a research release

**Work required**

1. Freeze the supported questions, protocols, models, evaluators, thresholds and limits.
2. Produce a replication package with approved data-access instructions, manifests,
   split and generator versions, source snapshots, dependency locks, seeds, numerical
   outputs, sanitized traces, checksums, failures and reproduction commands.
3. Have an independent reader reproduce the declared end-to-end workflow from a clean
   environment, using documented tolerances for permitted nondeterminism.
4. Review licenses, provenance, privacy and redistribution permissions before any release.
   Never publish credentials, raw sensitive records or proprietary employer material.
5. Write a technical report with baselines, ablations, effect sizes, uncertainty, costs,
   limitations and negative results. Assess novelty through a primary-source literature
   review before making a paper or publication-readiness claim.

**Gate:** A reader can reproduce the supported results, inspect their evidence, understand
their limits and distinguish implemented features from planned ones. Publication and
external deployment remain separate authorized actions.

## 7. Practical completion checklist

| Area | Evidence required before calling the declared release complete |
|---|---|
| Scope | Supported questions, datasets, evidence levels and exclusions are documented |
| Data | Rights, provenance, validation, temporal availability and construction rules are recorded |
| Tools | Each registered method has prerequisites, known-answer checks and meaningful failure tests |
| Research validity | Hypotheses, baselines, metrics, budgets and stopping rules are frozen where required |
| Leakage | Future information, held-out targets and evaluator answers are inaccessible to agent roles |
| Claims | Every factual conclusion links to verified evidence; unsupported wording triggers rejection or qualification |
| Evaluation | Human-reviewed independent scoring, fresh cases, useful-discovery coverage and failures are reported |
| Uncertainty | Any probabilistic or interval claims have the appropriate adequacy and calibration evidence |
| Causality | Causal outputs require identification; unsupported requests lead to explicit abstention |
| Operations | Budgets, receipts, interruptions, cancellation and recovery behave as documented |
| Security | Actual containment matches the declared threat model; no arbitrary model-generated execution |
| Reproduction | A clean end-to-end reproduction succeeds with versioned inputs and recorded tolerances |
| Release | Licenses, privacy, documentation, limitations and publication permissions are reviewed |

Only applicable features belong in a release's checklist. A descriptive release need
not contain a GNN or causal estimator; it must not imply those capabilities exist.

## 8. Next smallest task

Start with blinded human review of the Sprint 3 claims and a recorded disagreement
analysis. Use it to define a narrow reliability improvement, freeze its evaluation on
fresh cases and measure whether it actually helps. Address known operational defects
alongside that work before expanding autonomy.

In parallel planning, define which one additional investigation would make the system
useful to a real intended user. Give that investigation an input contract, a simple
baseline, an evidence standard and a reproducible completion test. This is how the
project can grow from a reliable narrow tool into a broader research platform.

## 9. Source documents and status interpretation

- [Project context](../PROJECT_CONTEXT.md): original ambition, research questions and scientific rules.
- [Sprint 1](../sprints/SPRINT_01.md): initial vertical-slice plan and historical dataset contract.
- [Sprint 2](../sprints/SPRINT_02.md): resumable workflow scope and acceptance requirements.
- [Sprint 3](../sprints/SPRINT_03.md) and [report](sprint03_report.md): completed offline scope and measured limitations.
- [Decision log](decision_log.md): recorded authorizations, changes, failures and evidence.
- [Full-dataset protocol](../protocols/full_dataset_experiment.md): separate exploratory scope now present in the working tree.

Some original planning documents still describe the initial handoff state. Use the
latest applicable decision, protocol, actual implementation and run artifacts together
when assessing current capability. This roadmap does not silently supersede a frozen
experiment or turn a proposed future stage into completed work.
