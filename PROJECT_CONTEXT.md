# BLACKGRID — project context

Status: planning handoff, 17 October 2026. This package defines future work; no platform implementation or experiment results are included. Read alongside `AGENTS.md` and `sprints/SPRINT_01.md`.

## Purpose and provenance

Build an autonomous network-science research platform that can formulate hypotheses, choose justified methods, execute bounded experiments, assess uncertainty, critique evidence, and produce reproducible reports. The goal is research depth and measurable scientific reliability, with a credible portfolio demonstration and a possible paper only if novelty and results justify it.

Source: the user's “Design Deeptech Portfolio Project” conversation (ID `6ad32413-cbec-83ee-8e0f-351c8ceb7a4b`) and the current handoff request. The original assistant proposed the provisional name NEXUS; the user selected **BLACKGRID**. Some later source responses resolve only as content-reference placeholders; this document does not claim to reconstruct them. Architecture choices, budgets, and acceptance thresholds below are proposed defaults, not prior user commitments or established findings.

Preserve the full ambition: agentic AI, network science, graph ML, Bayesian uncertainty, causal inference, scientific experimentation, LLM evaluations, inference optimization, and LLMOps. Sequence these around one testable contribution instead of implementing every technology at once.

## Research thesis and scope

Primary question: **Does adding statistical validation and uncertainty-aware criticism to a tool-using research agent reduce unsupported conclusions while preserving useful discoveries under equal resource budgets?**

Start with CollegeMsg as the Sprint 1 real-data demonstration, paired with small synthetic communication-style networks for correctness and known-truth evaluation. CollegeMsg is selected; its usage and redistribution terms still need verification before analytical use or release. Organizational networks are a motivating example, not permission to ingest employee data. Co-employment is not evidence of interaction; centrality is not observed influence, trust, expertise, or causal importance.

The first demonstration should take a research question and a small graph, propose an allowlisted experiment, execute it, and return a claim linked to artifacts, uncertainty, limitations, and an abstention where appropriate. Avoid unrestricted discovery, real-world interventions, individual profiling, and claims of general scientific intelligence.

## Sprint 1 dataset: CollegeMsg

- Local immutable input: `C:\Blackgrid\data\CollegeMsg.txt\CollegeMsg.txt`; configure the repository-relative path `data/CollegeMsg.txt/CollegeMsg.txt` for portability. Do not rename, overwrite, or reorganize raw datasets during this sprint.
- Source and semantics: [Stanford SNAP CollegeMsg documentation](https://snap.stanford.edu/data/CollegeMsg.html). Rows are whitespace-separated `source_id target_id unix_timestamp`; each row records a directed messaging event. The original study is Panzarasa, Opsahl, and Carley (2009), linked/cited by SNAP. Record the source, citation, checksum, and rights review in the data manifest. Public download availability does not establish an open license.
- Inspect the local file rather than assuming it exactly matches the published release. Check integer fields, malformed rows, timestamp order/range, self-loops, repeated pairs, and exact duplicate rows. Preserve repeated events; flag exact duplicates without silently deleting potentially genuine messages.
- Select the earliest complete 7-day window starting at the minimum valid timestamp, using a half-open interval `[t0, t0 + 7 days)`. If that exceeds 1,000 active nodes or 10,000 unique undirected pairs, use 3 days, then 1 day, then 6 hours, choosing the first window within both caps. Base this choice only on size, before examining community results. If none fits or the graph is unsuitable for inference, abstain and record the limitation; do not select a favorable window.
- Preserve the selected directed event table and timestamps. For the one Sprint 1 community experiment, derive a simple undirected unweighted graph: connect a pair if at least one message occurred in either direction, aggregate repeated/reciprocal events into one edge, and exclude self-loops from this projection while recording counts. This tests communication connectivity only, discarding frequency and direction by explicit design. Record the projection hash, time bounds, exclusions, active-node count, and unique-edge count. No claim applies to unobserved/non-active users or the full dataset automatically.
- Community memberships and causal effects have no supplied ground truth. Report exploratory structural findings separately from synthetic benchmark scores; never claim verified friendship groups, influence, or causal effects. Treat identifiers as pseudonymous, avoid re-identification and individual profiling, and keep raw records out of external LLM prompts and telemetry.
- Keep the other local datasets (Bitcoin OTC, Reddit, Wikipedia talk, and Stack Overflow) out of Sprint 1. Full-dataset profiling may stream the small CollegeMsg file, but bounded graph experiments use only the recorded window. No prediction model or temporal train/test benchmark is needed this sprint.

## Scientific contract

Every investigation records:

1. Question, hypothesis, competing explanations, graph semantics, and evidence level.
2. Preregistered confirmatory protocol or explicit exploratory status.
3. Data provenance, observation window, construction rules, exclusions, and missingness assumptions.
4. Method justification, baseline, null model, estimand or target metric, and stopping rule.
5. Split identifiers, seeds, configurations, software versions, and resource limits.
6. Executed tool calls, failures, outputs, statistical uncertainty, and critic decisions.
7. Claims tied to specific results, limitations, and reproduction instructions.

Use evidence labels: descriptive observation; predictive association; simulation intervention under stated assumptions; identified causal estimate under stated assumptions; unsupported/insufficient evidence. A critic's approval is not independent scientific validation.

## Phased architecture and gates

Logical flow: question → constrained planner → validated experiment specification → deterministic tool executor → artifact store and evaluators → critic → evidence-grounded report. A bounded controller permits revision, abstention, or termination. Planner, analyst, and critic are roles; initially they may share one process and model. Six separate agent services are unnecessary.

| Phase | Minimal capability | Gate before expansion |
|---|---|---|
| 0: protocol and data | CollegeMsg manifest/loader/window contract, synthetic generators, benchmark specifications, reproducibility manifest | Ground truth, splits, oracle tests, and resource limits reviewed |
| 1: reliable vertical slice | Bounded CollegeMsg demonstration plus synthetic checks, network summaries, null-model experiment, agent, report | One offline reproducible end-to-end run; unsupported claims and failures visible |
| 2: controlled scientific agent | Statistical validator, critic, missing-edge sensitivity, blinded held-out evaluation | Paired ablation study reports validity and useful discovery, including null results |
| 3: graph prediction | Heuristics before embeddings; add one GNN only if justified | Leakage-safe protocol and meaningful comparison against tuned simple baselines |
| 4: Bayesian uncertainty | Explicit probabilistic model, prior checks, posterior predictive checks, calibration | Coverage and model adequacy evaluated; distinguish posterior, bootstrap, and sensitivity intervals |
| 5: causal extension | Estimand and identification review; synthetic structural causal models first | Identification assumptions and interference addressed; observational claims constrained |
| 6: efficiency and operations | Tracing, regression gates, routing, caching; serving optimization if needed | Quality/cost/latency comparison at fixed workloads; security and rollback checks |
| 7: research release | Frozen benchmark, public-data validation, replication package, technical report | Claims match evidence; licenses, reproducibility, and limitations reviewed |

These are dependency gates, not fixed calendar promises. Basic traces, cost accounting, provenance, and security begin in phase 0; they are not postponed until phase 6.

## Small initial technical shape

Proposed starting point: Python, a single graph library such as NetworkX, ordinary statistical tools, file-based JSON/Parquet artifacts, a small CLI, one provider adapter with mock mode, and focused tests. Lock dependencies and record the runtime. Choose exact packages when implementation is authorized and compatibility can be checked.

Future candidates: PyTorch Geometric for a justified GNN, PyMC for Bayesian models, a causal library after identification, and an experiment tracker when local manifests become inadequate. LangGraph, vLLM, external tracing platforms, APIs, databases, Docker, and dashboards are optional decisions driven by demonstrated needs. Do not introduce Kubernetes, Ray, a graph database, microservices, or a model zoo for the first slice. Verify available RAM/VRAM and operating-system support before local-serving choices; no hardware assumption is a requirement.

Suggested future repository areas: `src/blackgrid/`, `tests/`, `configs/`, `protocols/`, `benchmarks/`, `data/manifests/`, `runs/`, and `docs/`. This is a proposal, not an instruction to scaffold them during handoff preparation.

## Research questions and benchmark design

| Question | Comparison | Outcomes |
|---|---|---|
| RQ1: Does criticism improve scientific reliability? | Same model/tools with validator and critic ablations | Unsupported-claim rate, task success, discovery recall, abstention, cost |
| RQ2: Does uncertainty help with incomplete graphs? | Point-estimate planner versus uncertainty-aware planner | Error/calibration under missingness; robustness of conclusions |
| RQ3: Can agents select valid methods? | Rule-based selector versus agent | Prerequisite violations, justified selection, valid experiment completion |
| RQ4: Does graph ML add predictive value? | Heuristics, simple learned model, then one representation model | PR-AUC, ranking metrics, calibration, time and memory |
| RQ5: Can routing reduce cost without degrading reliability? | Fixed model versus budget-aware routing | Prespecified quality non-inferiority, cost, latency, failure rate |
| RQ6: Can the system recognize non-identification? | Identifiable and non-identifiable causal scenarios | Correct abstention, assumption disclosure, bias/coverage where truth is known |

RQ1 is primary. RQ2 is the first extension. RQ3 is a supporting diagnostic; RQ4–RQ6 wait for their phase gates.

### Controlled benchmark

Use synthetic graph families with independent generated instances: Erdős–Rényi nulls, planted-community stochastic block models, degree-heterogeneous networks, and disconnected/sparse edge cases. Vary size, density, signal strength, and observation quality. State when a generator's latent labels differ from an algorithm's community objective. Degree-preserving nulls should preserve nuisance structure when relevant.

Task families: assess evidence of community structure; test a prespecified structural claim against a suitable null; distinguish incomplete observation from plausible fragmentation; refuse invalid methods and unsupported causal claims. Temporal prediction tasks require an actual event-time generator or suitable real temporal data, not timestamps pasted onto a static benchmark.

Pilot scope: 8 small synthetic development cases plus separate CollegeMsg parser/window fixtures across at least three graph families and four task types. These are engineering fixtures, not evidence of efficacy. A later confirmatory suite should start at roughly 60 independent instances, with sample size revised using pilot variance and a prespecified precision/power objective. Repeated model samples on the same graph are not independent graph instances.

Compare: deterministic rule-based baseline; conventional LLM without execution tools; tool-using LLM; tool-using LLM plus statistical validator; full uncertainty-aware critic. Add a full-minus-uncertainty ablation to separate criticism from uncertainty. Keep prompts, tools, model version, task inputs, budgets, and stopping rules comparable; disclose unavoidable differences. Match maximum budgets, record actual consumption, and inspect quality/cost tradeoffs.

Separate development, validation, and sealed test graph instances, seeds, and prompt templates. Hold out a graph family for generalization when feasible. Generator truth and answer keys stay inaccessible to the planner, critic, and report generator. An independent evaluator may read them. Freeze prompts, evaluators, model identifiers, thresholds, and budgets before test execution. Corrections after test inspection require a new test set or explicit exploratory labeling.

### Scoring and statistics

- Primary: unsupported factual conclusions divided by all assessable factual conclusions, using a frozen claim-segmentation and support rubric. Report numerator, denominator, task-level aggregation, and abstentions.
- Prevent trivial abstention wins: also measure valid discoveries recovered, task completion, and coverage-risk curves. Report omissions separately from false claims.
- Measure empirical false discovery proportion on synthetic tasks with known truth; reserve “FDR control” for a procedure and assumptions that actually justify it. Record all attempted hypotheses, including unsuccessful ones.
- Use effect sizes and uncertainty intervals, paired comparisons on the same instances, and graph-level resampling. Do not treat nodes, edges, or repeated agent responses as independent when dependence invalidates that assumption.
- Prespecify alpha, multiple-testing family, correction method, and optional-stopping policy. Use a fresh confirmatory set after adaptive exploration; a critic cannot repeatedly test until significance appears.
- Test numerical tool outputs against independent oracles on tiny cases. Use blinded human review on a declared subset and disagreements. LLM judging is a supplementary, versioned evaluator; evaluate its agreement and avoid self-grading as sole ground truth.
- No success margin is asserted today. Before confirmatory execution, set a minimum useful reduction in unsupported claims, an allowed loss in discovery recall, and a precision target using pilot evidence.

## Mandatory validity guardrails

### Leakage and graph prediction

For temporal tasks, split by event time and respect availability time: training features, topology, embeddings, imputers, preprocessing, and tuning must use only information available at the prediction cutoff. Validation precedes test. Remove held-out target edges from message passing and feature computation; keep reverse and duplicate edges together. Declare transductive versus inductive scope, node overlap, cold-start handling, and entity-disjoint splits when required by the claim.

An unobserved edge is not a confirmed negative. Define candidate universe, observation horizon, censoring, negative sampling distribution, and whether future positives could be sampled as negatives. Evaluate more than easy random negatives; disclose class prevalence and use PR-AUC and ranking metrics with the candidate protocol. Tune all models on validation under comparable budgets. Bootstrap at an appropriate graph/time block level.

### Missing edges and uncertainty

Distinguish observed interactions, inferred/proxy links, absent observations, known non-links, and uncertain links in the data contract. Record direction, weight meaning, timestamps, collection mechanism, and provenance. Never silently promote proxy edges into observed evidence.

Stress-test uniform edge removal plus degree-, group-, or time-dependent missingness; include plausible missing-not-at-random scenarios. Sensitivity to assumptions is not recovery of hidden truth. Keep graph-construction, sampling, parameter, and model uncertainty distinct. Evaluate probability calibration with Brier/log scores and reliability plots; evaluate interval coverage where repeated simulated truth exists. Never label arbitrary model scores as probabilities or bootstrap intervals as Bayesian credible intervals.

### Causality

Specify treatment, outcome, unit, time ordering, estimand, candidate DAG, confounders, selection, positivity, and measurement limitations before estimation. Network interference and spillovers can violate independent-unit assumptions; define exposure mapping or restrict the claim. Causal discovery and predictive performance do not establish identification. An LLM-generated DAG is a hypothesis.

Use synthetic structural models to test known interventions first. On real observational data, require an identification argument and sensitivity analysis for unmeasured confounding; otherwise report association and abstain from a causal estimate. Even a valid simulation intervention supports only the assumed simulator. Do not recommend interventions affecting people from exploratory network patterns.

### Synthetic versus real evidence

Synthetic experiments establish behavior under specified generators, not real-world validity. Public real data may support descriptive or predictive validation but rarely supplies causal or scientific-discovery ground truth. Keep score tables separate, document domain shift, and avoid pooling them into a misleading headline. Check licenses, collection ethics, access conditions, and redistribution rights before downloading or publishing a dataset. CollegeMsg is selected for Sprint 1; its license/usage terms are not yet verified. Record that review before analytical use; if rights remain unresolved, retain the selection but mark the real-data run blocked and finish the synthetic correctness workflow. Do not redistribute raw CollegeMsg records without verified rights.

## Reproducibility and operations

Each run needs a unique ID; UTC timestamps; source commit and dirty-diff status; runtime/dependency lock and hardware; dataset and split hashes; generator and graph-construction version; seed hierarchy; configuration hash; prompts and model/provider revision; tool versions; sampling parameters; sanitized tool traces; token usage; estimated and actual cost; elapsed time; artifacts and checksums; and final evidence links. Preserve failures and cancellations.

Separate raw read-only data, derived data, and run artifacts. Record transformations as executable steps. Provide one documented reproduction command when implemented. Fixed seeds reduce variance but do not guarantee bitwise determinism, especially for hosted LLMs and GPU kernels. Record nondeterminism and permit tolerance-based scientific checks; retain permitted raw responses for replay.

LLMOps begins with local structured traces, versioned prompts/evaluations, schema validation, and regression fixtures. Later route or cache by task and model/config version with data-bound keys; isolate answer keys and private data. Benchmark warm/cold caching separately. Compare quantization, batching, or serving changes on the same quality suite and workload, reporting latency distributions, throughput, memory, hardware, concurrency, and cost. Speed gains alone do not justify degraded scientific reliability.

## Resource and security defaults

Planning this package spends no API or cloud budget. Proposed first-sprint implementation budget, if later authorized: 16–20 focused hours total; CPU-first, experimental graphs at most 1,000 nodes/10,000 unique edges (CollegeMsg uses the deterministic window above); one concurrent experiment; 2 GB worker memory and 60-second tool timeout as initial adjustable limits. Use deterministic mock/replay first.

Proposed paid pilot ceiling: USD 10 total, USD 0.50 per investigation, at most 8 LLM calls and 20,000 total input/output tokens per investigation, at most one retry per failed call, and at most two revise/critique rounds within those limits. These ceilings do not authorize paid services. Require explicit approval before paid access or cloud provisioning. No GPU rental in sprint 1. Stop before the next call would exceed the most restrictive limit; if price is unknown, disable paid execution. Log estimates/reservations and reconcile actual usage; count retries and failed billable calls. Budget exhaustion is a recorded outcome.

Run only registered tools with validated structured arguments. Treat dataset text, retrieved content, and model output as untrusted data. No arbitrary generated Python or shell execution. Workers need enforced wall-time, CPU/memory/output limits, an isolated working directory, read-only inputs, no secrets, no host mounts beyond explicit needs, and network denied by default. A Python subprocess alone is not a security sandbox. If containment is unavailable, use only trusted deterministic tools and do not run untrusted code.

Keep credentials in environment or a secret store, outside prompts, traces, datasets, and version control. Redact logs and minimize retained personal data. Require authorization for external writes, publication, account changes, broader network/filesystem access, and real-world actions. Use dependency locks and license/security review before release. Trace destinations themselves are data disclosures and need review.

## Clean-room boundary

BLACKGRID must contain **no proprietary ValueMatrix code or data**: no copied implementations, private schemas, prompts, weights, evaluation sets, employee/customer records, derived graphs, embeddings, screenshots, credentials, or confidential business logic. Do not inspect private work directories to recreate them. General knowledge may inform independently written methods; use public literature and licensed public/synthetic inputs with provenance. If origin or rights are unclear, quarantine the material and ask before use. Keep a provenance/license ledger for all imported assets and dependencies.

## Deferred decisions and release expectations

Resolve during implementation planning: CollegeMsg usage/redistribution terms and suitability of its prespecified window, machine capacity, provider permissions, literature-based novelty, confirmatory sample size, and useful-effect threshold. A focused primary-source literature review should inform novelty claims; none is made here.

Target eventual artifacts: a small working platform, frozen benchmark and ablations, reproducible runs, model/data documentation, an evidence-grounded demo, and a technical report including failures. A polished interface and preprint follow evidence, not the reverse. Begin with the bounded 14-day plan in `sprints/SPRINT_01.md` only after a separate request to implement.
