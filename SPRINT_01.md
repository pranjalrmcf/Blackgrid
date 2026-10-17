# BLACKGRID — sprint 01

Duration: 14 days from an agreed implementation start; no fixed start date. Planning capacity: 16–20 focused hours total, usually 60–90 minutes per workday with a longer integration session. Scope may be reduced to fit actual availability. This document does not start implementation or authorize spending.

## Sprint outcome

Deliver one local, reproducible investigation of a bounded CollegeMsg messaging graph, with synthetic known-truth checks: a constrained agent selects a valid community-structure experiment, deterministic tools execute it, a critic checks the evidence, and a report either supports a narrowly stated conclusion or abstains. Provide a deterministic mock mode requiring no paid API. A live LLM run is optional after authorization and is not required for sprint completion.

Research anchor: “Is the observed community structure stronger than expected under an appropriate null, and how sensitive is the conclusion to missing edges?” This is an exploratory pilot for RQ1/RQ2, not a claim that the architecture improves science.

Do not implement graph ML, full Bayesian inference, causal estimation, custom serving, multi-agent services, a UI, or deployment. Preserve their later phase gates in `PROJECT_CONTEXT.md`.

## Selected data and graph contract

Use `data/CollegeMsg.txt/CollegeMsg.txt` in this repository (currently `C:\Blackgrid\data\CollegeMsg.txt\CollegeMsg.txt`). The [SNAP source documentation](https://snap.stanford.edu/data/CollegeMsg.html) defines directed message events with source, target, and Unix timestamp. Record a local SHA-256, source/citation, schema checks, and usage/redistribution review. Raw files remain unchanged; do not send identifiers or event records to an external LLM or tracing service.

Follow the deterministic window rule in `PROJECT_CONTEXT.md`: earliest 7 days, falling back to 3 days, 1 day, then 6 hours solely to meet 1,000-active-node/10,000-unique-edge limits. Freeze the selected bounds and graph construction before inspecting experimental outcomes. If none fits or inference is unsuitable, record an abstention rather than cherry-picking a window.

Preserve directed repeated events in the selected event table; derive a simple undirected unweighted graph for the single community experiment. Aggregate reciprocal and repeated pairs; omit and count self-loops. Record all validation decisions and exclusions. The inference concerns this projected observed window only. Synthetic fixtures retain known truth; CollegeMsg supplies no verified communities or causal ground truth. If usage rights remain unresolved, mark the CollegeMsg acceptance criterion blocked and complete synthetic checks without claiming the real-data demonstration is done.

## Minimal experiment specification

Use the bounded CollegeMsg projection for the real-data demonstration and small planted-community/null graphs with degree-heterogeneous controls for correctness checks. Preselect a community method and statistic; distinguish its objective from latent generator labels. Compare against a documented degree-preserving null where feasible, with explicit handling of disconnected graphs, small graphs, swaps that fail, and Monte Carlo resolution. Do not interpret a small p-value as effect size or proof that communities exist in a substantive social sense.

Apply the same community detection and statistic-computation procedure to the observed graph and every null graph, with documented seeds and comparable optimization effort; do not compare an optimized observed partition against unoptimized null partitions.

Use a fixed null-replicate count selected on development cases within the tool-time cap; record it and report the attainable p-value resolution, for example `(1 + exceedances)/(1 + replicates)`. Do not reduce replicates opportunistically after seeing significance. Report the observed statistic, null distribution summary, effect contrast, uncertainty/limitations, and sensitivity to a prespecified edge-removal condition. Formal Bayesian intervals are deferred; label missingness sweeps as sensitivity analysis.

The report must say when evidence is inconclusive. An invalid or underpowered experiment should fail or abstain, not yield a forced conclusion. Treat planted labels as evaluator-only metadata.

## Day-by-day plan

| Day | Approx. hours | Work and tangible acceptance evidence |
|---|---:|---|
| 1 | 1 | Confirm the CollegeMsg task, source/citation and usage terms, graph/window contract, machine limits, and sprint scope. Write a short protocol and decision log. No private data or paid service needed. |
| 2 | 1 | Create the minimal repository and locked environment after authorization. Define graph, experiment, result, claim, and run-manifest contracts; document one offline entry point. |
| 3 | 1.5 | Implement the CollegeMsg loader, checksum/schema checks, and bounded window/projection. Add tiny seeded synthetic fixtures with evaluator-only truth and stable hashes. |
| 4 | 1 | Build 8 compact synthetic development fixtures covering three graph families and four task types, including null, disconnected, missing-edge, and invalid-request cases; add CollegeMsg parser/window fixtures. Separate future sealed-test location and IDs. |
| 5 | 1.5 | Implement deterministic graph profiling and the one statistical experiment. Check results against hand-computable cases or an independent numerical oracle. |
| 6 | 1 | Add fixed missing-edge sensitivity cases and graph provenance. Demonstrate that missing links are labeled unknown and proxy links stay distinguishable. |
| 7 | 1 | Implement validated experiment specifications and allowlisted execution with resource limits. Reject arbitrary code, invalid methods, oversized inputs, and malformed arguments. |
| 8 | 1.5 | Add one bounded planner/controller with mock responses and an optional provider adapter. Enforce call, token, retry, revision, cost, and deadline limits before execution. |
| 9 | 1 | Add a deterministic validator and critic rubric: method prerequisites, statistical support, limitations, and claim/evidence links. Include unsupported causal-claim rejection. |
| 10 | 1 | Generate a CollegeMsg Markdown report plus structured run artifacts, with observed-window limitations and separate synthetic correctness results. Test that no unsupported number enters the report and that failures/abstentions remain visible. |
| 11 | 1.5 | Run matched tool-only versus validator/critic pilot fixtures in mock mode. Score schema, workflow, support rubric, useful coverage, and failures; do not infer LLM efficacy from mocks. |
| 12 | 1 | Exercise prompt-injection-like text, answer-key access, denied network, timeout, and budget-stop scenarios. Verify actual enforcement or explicitly disable unsupported execution paths. |
| 13 | 2 | Reproduce an offline end-to-end run in a clean environment using documented steps. Inspect report evidence, manifests, and failed-run artifacts. Repair only demonstrated blockers. |
| 14 | 1.5 | Review all acceptance criteria; publish a local sprint report with limitations, actual hours/costs, and next-phase go/no-go decision. Keep exploratory findings separate from research claims. |

Total planned effort: 17.5 hours, leaving roughly 2.5 hours of contingency within the 20-hour ceiling. If integration slips, drop the optional provider adapter/live run first, then reduce fixture breadth while documenting missing coverage. Do not trade away evidence links, split isolation, resource stops, or reproducibility. Mark unfinished criteria explicitly rather than claiming completion.

## Required outputs when implemented

- A minimal offline CLI workflow and documented reproduction command.
- Versioned CollegeMsg loader/window/projection contract and rights/provenance manifest, plus synthetic generator configuration and development fixtures.
- One experiment protocol, deterministic implementation, baseline, and critic rubric.
- Planner mock, validated tool registry, bounded controller, and failure/abstention paths.
- A CollegeMsg example report and structured manifest with input/projection hashes, time bounds, validation/exclusion counts, and sanitized traces; separate synthetic results.
- Focused tests, a short pilot evaluation table, and an honest sprint report.

These are future deliverables. This handoff contains no code and asserts no tests or experiments have run.

## Definition of done

1. A clean offline CollegeMsg run completes from the existing local file using documented instructions without secrets, downloads, or network calls, after usage terms are verified. If terms remain unresolved, mark this criterion blocked; a synthetic-only run is partial completion.
2. Small known-answer and null fixtures validate numerical tools and invalid-input behavior. A positive fixture does not require every stochastic run to be significant.
3. Every factual report claim links to recorded evidence; an insufficient-evidence case abstains and an unsupported causal statement is rejected.
4. Generator truth and held-out metadata are excluded from all planner/critic/report inputs, with a test that attempts access.
5. Run artifacts record configuration, versions, seeds, hashes, tool calls, failures, timings, and zero/mock versus actual monetary cost accurately.
6. Budget exhaustion, excessive retries, timeout, oversized graph, malformed tool call, and unauthorized execution terminate predictably with sanitized artifacts.
7. The pilot reports both unsupported claims and useful coverage, with denominators. Mock outputs validate plumbing only; any real-model results are labeled small exploratory observations.
8. Missing-edge sensitivity and CollegeMsg observation/projection limitations appear in the report; synthetic scores remain separate. No proprietary ValueMatrix data, added identity information, or raw user/event records appear in external prompts, telemetry, or published reports.
9. Loader checks cover malformed rows, repeated events, exact-duplicate flagging, self-loops, and timestamps. Tests verify deterministic window selection and pair aggregation; the manifest records raw and projected counts. No result-dependent window selection occurs.

## Budget and stop rules

Use the defaults in `PROJECT_CONTEXT.md`: CPU-first; experimental graphs at most 1,000 active nodes/10,000 unique edges using the CollegeMsg window rule, one worker, 2 GB worker memory, and 60 seconds per tool. Begin smaller if null replicates exceed limits. No cloud GPU, infrastructure accounts, or unattended paid loops.

Paid usage requires separate authorization. If authorized, enforce USD 10 sprint total, USD 0.50 per investigation, 8 LLM calls, 20,000 total tokens, one retry per failed call, and two revision rounds, all inclusive. Halt before exceeding any cap; do not interpret retries or subcalls as free. Record the current provider price and reservation calculation; disable paid paths when pricing is unavailable. These are planning ceilings, not price quotations.

## Sprint review and next step

Go forward only if deterministic results, evidence linkage, containment, and offline reproduction work. Repair the harness before expanding if they fail. A lack of measurable critic improvement is a valid result and may motivate a simpler rule-based system.

Next smallest research step: freeze a live-model pilot protocol and evaluator rubric, obtain any required API authorization, estimate variance and costs, then choose confirmatory sample size and useful-effect thresholds before opening a fresh test set. Review CollegeMsg window suitability and any remaining usage/redistribution restrictions before broader public-data validation; keep the other datasets deferred. Graph ML, Bayesian modeling, causal inference, and serving optimization remain later experiments, each requiring its own justification and acceptance gate.
