# Repairs following current-system evaluation v4

The four evaluated error classes are addressed. The original v4 result remains 17/24; the following development checks do not replace or rescore that evaluation.

## Changes

- Forecast artifacts now record full observed-history scope, history node/pair counts and cutoff. Reports use those values instead of the structural input's first-window label. Historical split, rolling-window count and external confirmation scope come from evaluation artifacts; obsolete two-window boilerplate is removed.
- Centrality sensitivity computes degree and betweenness stability on the same three registered uniform removals. Both metrics are named and displayed. Structural contracts/cache identity are versioned to prevent old betweenness-only results being reused as complete answers.
- Bridge reports define the connector score as the number of neighbours outside the participant's saved community, and explain cross fraction.
- Planner instructions request compact JSON and a short reason. Live output caps are 8192 with reasoning still bounded at 1024. This reduces truncation risk but cannot guarantee every future planner response succeeds.
- Validated community/structural factual summaries use local evidence templates, as forecasts already did. The real LLM still plans, registered tools execute, and existing critics and report checks remain active. No mock provider replaces the model. Tool-only comparison behavior remains separate.

## Executed verification

50 focused checks passed across the new repair tests, HTTP limits, semantic routing, intent boundaries and live allowance. Another 13 selected direct structural tests passed, covering independent betweenness, star ranks, bridge counts, partition coverage, sensitivity semantics, prerequisite rejection, cache identity and sampled estimates. No mock-model execution was used. New regression fixtures are self-contained and require no saved live runs.

First frozen development phase: five live attempts, three passed, one analyst response truncated and one analyst request timed out with uncertain billing. These records remain unchanged in `runs/error-repairs-v5/`. That result showed increasing the output cap alone was insufficient. No uncertain operation was resumed or resent.

After the local-summary change, a separately frozen confirmation phase completed the community, dual-centrality-sensitivity and connector-explanation questions: **3/3 passed**, 9.50 seconds overall. Each used one real planner call. Both forecast tasks passed separately in the first phase; the subsequent summary change leaves the forecast branch intact.

Artifact hashes, reported claim values, report number bindings and requested semantic targets were checked independently of the running LLM. Community null arithmetic was independently checked. Source hashes remained unchanged within each execution phase. Audit: [audit.json](../runs/error-repairs-v5-confirmation/audit.json).

## Resources and limitations

Both phases combined: USD 0.00649908 receipted, USD 0.00879000 retained for one uncertain call; conservative incremental total USD 0.01528908. Project accounted total USD 1.35661364, including prior charges/reservations, within USD 3. No reserved charges were erased.

This is development verification on inspected questions, not a fresh 24-case evaluation or a new scientific generalization result. Normal numerical caches and saved predictive evaluation were reused. Cold community computation in the first phase recomputed the fixed null/sensitivity analysis after cache versioning; confirmation reused that evidence. Provider availability and future planner truncation remain possible failure modes and retain explicit failure/paused outcomes. Exact floating-point ties can depend on numerical accumulation order; no broader tie-policy change is claimed here.

The next smallest task is a new frozen evaluation of the final version if a new overall success estimate is needed. No additional paid evaluation is running.
