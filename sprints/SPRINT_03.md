# BLACKGRID - Sprint 3: give the research agent a fair exam

Date: 18 October 2026. Implementation authorized in chat. Six sessions / approximately 14 focused hours is a planning estimate, not measured human effort.

## Completion status — 18 October 2026

The planned offline scope is implemented: 24 fresh synthetic instances, 48 paired
mock investigations, 54 real CPU Louvain–Leiden graph-seed comparisons, independent
artifact scoring, an 81-claim blinded export, full CollegeMsg ingestion, and a
plain-English guide. See [the results report](../docs/sprint03_report.md) for measured
outcomes, verification, reproduction receipts and preserved failures.

The corrected protocol is `s3-v1.2`; prior validation inspection is disclosed. The
authoritative run is `runs/sprint3-v1.1`. Unsupported claims remain after criticism;
do not interpret engineering completion as research-thesis success. Human review and
any paid real-model trial are pending follow-ups. Louvain remains the default.

## Goal

Create fresh validation cases, measure useful answers and unsupported claims, and compare community methods under a new exploratory protocol. Preserve the earlier Louvain experiment and historical runs. Add full-file CollegeMsg ingestion and aggregate profiling at the user's request, while retaining the fixed first-week graph for historical scientific comparisons.

## Sessions

1. Freeze the evaluation and method-comparison rules; rerun Sprint 2 regression checks.
2. Generate 24 new validation instances with neutral IDs and private evaluator expectations. Leave sealed tests untouched.
3. Compare Louvain with a CPU Leiden adapter using modularity for both, shared randomized graphs, fixed seeds, and disclosed search effort.
4. Run matched offline agent conditions and independently score the saved artifacts. Export blinded claims for human review.
5. Inspect mistakes and retain original results. Do not tune against validation outcomes and claim those same scores as independent evidence.
6. Write a results report and a plain-English guide, including limitations and environment blockers.

## Boundaries

- Offline mock evaluation is a workflow check, not evidence that a critic improves an actual LLM. Paid calls need separate authorization.
- Local full CollegeMsg ingestion is authorized; no raw rows/IDs are exported or sent to a model. Other datasets remain deferred.
- Full-file ingestion does not remove the existing 1,000-node experimental limit or change a frozen time window.
- No automatic Leiden default switch, new agent framework, prediction model, or dashboard redesign.
- Dependencies unavailable in this session must be recorded as unavailable; never substitute Louvain and call it Leiden.
- Existing employer-data, causal-language, leakage, reproducibility, and spending safeguards still apply.

## Completion evidence

Source and tests, versioned protocol, deterministic validation registry without answer keys, independent evaluator tests, method-comparison output with explicit backend status, full-file aggregate ingestion manifest, matched mock evaluation, blinded review export, and a report distinguishing measured results from pending work.

Any inability to install/run Leiden or apply changes to the original directory is a remaining requirement, not a completed comparison or deployment.
