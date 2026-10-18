# Sprint 5: bounded structural investigations

Follow-up: real AI integration, the revised console and paid development checks are documented in [the live report](sprint05_live_report.md). The USD 0 statement below refers to this original offline implementation.

Implemented on 18 October 2026. Paid spend: USD 0. No new dataset, infrastructure or dependency was added.

## Delivered behavior

The agent-facing arsenal grows from three to seven tools. Centrality and bridge questions have separate requirements from community significance questions. The workflow supports one evidence-inspection/follow-up round, preserving the existing durable operations, resource reservations, cancellation, replay and ownership checks.

The new tools compute degree/betweenness, descriptive Louvain partitions, cross-community connections and ranking stability. Typed structural contracts record their fixed settings. Local node rows are kept out of model evidence. Structural answers use registered evidence-bound claim forms; unfamiliar prose is unassessed rather than accepted by default. Existing community claim rules remain narrow and are not a general semantic verifier.

The existing console now supports question entry, examples, sortable local rankings, partition/sensitivity metadata, a follow-up explanation, compatible-run summary comparison and expandable evidence values. No hosted interface, arbitrary code execution, multi-service agents or prediction model was introduced.

Versions are prompts-v6, critic-v6 and tools-v2 with structural-v1. Older paused runs remain protected by version/identity checks; start a new run with a parent reference rather than bypassing them. Existing cached computations use a different tool-version identity; historical results remain intact.

## Evaluation and reproduction

The engineering protocol was frozen before generating 16 new synthetic instances. Each instance was evaluated under a deterministic router, single-plan scripted mock and adaptive scripted mock. All share the numerical executor and checks; this is not a real-LLM comparison.

| Recorded result | Deterministic router | Single plan | Adaptive |
|---|---:|---:|---:|
| Useful completed answers, including four correct refusals | 16/16 | 16/16 | 16/16 |
| Independently scored numerical/evidence errors | 0 | 0 | 0 |
| Unsupported reported claims under the fixed vocabulary | 0/36 | 0/28 | 0/36 |
| Scripted model/rule calls | 28 | 28 | 40 |
| Tool invocations | 30 | 22 | 30 |
| Estimated input/output tokens | 23,836 | 20,687 | 31,527 |
| USD | 0 | 0 | 0 |

All 48 attempts are retained. Degree and exact betweenness were checked independently against graph counts and the full NetworkX reference. Cross-community counts were recomputed from the saved partition. The evaluator verifies manifest hashes, claim/value/path bindings, required analyses and refusal before tools.

The first run is `runs/sprint5-v1` (34.48 seconds); its clean reproduction completed in 30.81 seconds. Browser inspection then exposed an undefined number formatter in the new ranking table, and the progress display omitted completed follow-up tools. Both were repaired without changing the numerical procedure. Original artifacts were preserved.

The disclosed **development rerun**, `runs/sprint5-v1.1`, completed in 29.73 seconds with the same aggregate scores. It reuses already-inspected instances and is not fresh validation. Its separately snapshotted clean reproduction completed in 29.11 seconds. All 48 saved scores and artifact checks match under `scripts/verify_sprint5.py`; timestamps, paths, run IDs and elapsed times are intentionally variable.

Clean reproduction used the locked offline dependency set in a separate environment (47 cached packages, no project installation), with an 83-file verified source/config snapshot. The 23 Sprint 5 tests also passed in that clean environment. Sandbox temporary-file replacement restrictions caused failed verification attempts; reruns outside those restrictions passed. Those environment failures are not scientific outcomes.

The final working-tree regression suite passed **302 tests in 203.57 seconds**. Focused checks cover known-answer graphs, ties, isolated/disconnected graphs, deterministic approximation, prerequisites, invalid arguments, evaluator-key refusal, cache corruption, private-node prompt exclusion, unknown prose, bounded follow-up, budget termination, interrupted follow-up recovery and replay.

Browser inspection verified synthetic ranking display, same-graph run comparison and claim evidence expansion. Synthetic identifiers were used for inspection. A real CollegeMsg first-week bridge run also completed offline at `runs/sprint5-demo/20261018T141543Z-599c6b`; this demonstrates execution only, and no individual-level findings are published here. The full dataset structural workload was not rerun during this sprint.

## Interpretation and remaining limits

The offline acceptance gates are met: supported question types execute through the shared workflow, unrelated community-null calculations are avoided, numerical outputs are checked and unsupported questions refuse before tools. The extra follow-up produces additional sensitivity facts when they were not originally required.

No measured quality advantage is established: all three scripted arms answer the required questions, while the adaptive arm makes more calls. The router is narrow, and model-generated structural prose is constrained to a small vocabulary. The live model's ability to choose a useful follow-up, adhere to the revised reasoning bounds and produce useful structural answers remains untested under this version.

Centrality is not causal influence. Partitions are not verified social groups. Sampled betweenness has no calibration guarantee. Uniform removal is one assumed missingness mechanism. Tools use cooperative deadlines and trusted code, not an OS security sandbox. Ranking payloads are capped for browser display, not paginated across all local rows.

The next smallest task is a separately frozen, explicitly budgeted real-model pilot of structural planning, using fresh questions/graphs and an independent review rubric. First measure whether the extra planning helps. Temporal prediction can follow with its own leakage-safe protocol and simple baselines; it is not needed to call this offline capability slice implemented.
