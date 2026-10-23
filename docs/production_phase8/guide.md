# Phase 8 operation and repeatable measurements

The existing service now uses cumulative `blackgrid:phase8`. Open the live dashboard with the same `scripts/open_dashboard.py` command and existing operator token. Submit questions with `scripts/ask_api.py` as before. Command-line progress adds **Cache: verified hit** when a completed graph tool reused a validated result. API job progress contains a bounded `cached` boolean for each tool.

`BLACKGRID_API_TOOL_CACHE=true` enables the optimization in Compose. Settings default to false outside this explicit deployment. To force fresh work for diagnosis, set the flag to false and recreate the service after checking it is idle. A new idempotency key creates a new job and planner call; it does not bypass the deterministic-tool cache. Reusing an old idempotency key returns the existing job and is not a new performance sample.

The cache is **not an LLM response cache**. Live calls still fetch approved pricing, invoke the configured provider and book charges under the retained limits. Questions still pass through the same agent, validation and claim rules. Do not expect lower LLM token charges from graph-result reuse. Forecast, behavioral-event and saved research tools continue to bypass the graph-only cache.

Mock and live modes use separate namespaces. The first live request can therefore be cold even after the free mock demonstration; later eligible live requests can reuse that live-mode graph cache.

Entries are private, owner- and mode-scoped beneath the existing API state volume. Base config, implementation, locked dependencies, Python/native runtime, graph projection, full experiment specification, arguments and prerequisite identity determine reuse. Changes invalidate the appropriate entries. Every new job still constructs and verifies its configured graph and validates tool prerequisites before lookup. No arbitrary request path or shared user-provided cache key is accepted.

Retention runs before/after jobs: at most 512 files/128 MiB are retained across owners, including quarantined/temp entries, with a seven-day age limit. A single active job can transiently add entries before post-job pruning; these are retention bounds, not an independent hard filesystem quota. Entries above 8 MiB, bad identities/checksums/schemas or links are rejected and recomputed. Cache-write/maintenance failures fall back to normal execution. Treat the cache as disposable private data; do not edit it or expose it through a static file server. It can contain graph-derived rows and remains part of private backups.

For deployment/recovery, retain the existing [Phase 7 runbook](../production_phase7/runbook.md). Restart retains valid cache entries but clears browser sessions. Rollback to Phase 7 uses the current job/billing volume and disables this optional optimization; never restore an older paid ledger to roll back an image.

## Reproduce the comparison

Use `scripts/benchmark_phase8.py --condition baseline` with the retained Phase 7 test image and `--condition candidate` with the Phase 8 test image, through `python -m scripts.benchmark_phase8` inside the container. Mount only the existing `phase6-inputs-v1/public` fixtures read-only at `/bench/public` and a new evidence directory at `/evidence`. The baseline also needs the current script and registered Phase 8 protocol mounted at their `/app/...` paths. Use 1 CPU/2 GiB/128 PIDs, no network, read-only root and bounded temporary state. See the executed commands in the task records and the [frozen protocol](../../protocols/production_phase8_v1.json).

Both conditions use the same fake credential registry and authenticated routes. Run baseline first; candidate reads its exact reference. Each output refuses to overwrite an earlier comparison. Preserve failures, raw logs, all samples and the separate prime job. A new rerun needs a fresh attempt/protocol record; do not silently replace the committed measurements. No host production data, provider key, live policy or generator truth is mounted.

Then run `scripts/report_phase8.py` to recompute medians/parity and derive the span breakdown from raw logs. The profiling helper is a separate bounded CPU diagnostic; its sensitivity-null budget is explicitly 19, whereas API comparisons retain the saved first-window workflow's 99 sensitivity nulls. It is not part of the uninstrumented latency sample.

Only three timed samples per condition were used. The ASGI client omits network/TLS effects and was sequential. A separate limited regression container ran during the candidate; this was not a dedicated-host experiment. Warm-cache results apply to repeated eligible work for that owner/config, not arbitrary new graphs, real inference or concurrent capacity. Do not extrapolate them into production SLOs.
