# Local monitoring and LLMOps

The current cumulative image is Phase 8. The live dashboard and tokens work as before; verified cache hits appear in job progress/command logs and reduce actual repeated tool timings. See [measured cache limits](production_phase8/report.md), [the Phase 7 residual security findings](production_phase7/report.md) and [incident runbook](production_phase7/runbook.md).

The current Phase 6 service includes a live browser dashboard. Open it with `.\.venv\Scripts\python.exe scripts\open_dashboard.py`, then sign in with the existing operator token. See [the live dashboard guide](production_phase6/guide.md) for sessions, charts and isolated benchmarks. The snapshot command below remains available.

Phase 5 adds monitoring to the existing HTTPS API and Docker service. It uses no additional dependency, service, paid request, outbound exporter or dashboard account. Run commands from `C:\Blackgrid`; activating the virtual environment is unnecessary.

```powershell
.\.venv\Scripts\python.exe scripts\monitor_api.py
```

This reads the current monitoring snapshot. For a readable dashboard saved locally:

```powershell
.\.venv\Scripts\python.exe scripts\monitor_api.py --dashboard
start .\tmp\blackgrid-monitoring.html
```

Open the printed HTML path. It is a snapshot: run the command again to refresh. The actual authenticated server page is `GET /api/v1/monitoring`, JSON is `/api/v1/monitoring.json`, and Prometheus text is `/api/v1/metrics`. Browsers need bearer authentication; the helper reads the existing private token and verifies TLS without exposing it in command arguments. The generated HTML contains aggregate operational data; keep it private. No browser storage, external assets, script, credential or model content is embedded.

```powershell
docker compose logs -f --tail=50
```

Command-line logs include structured request and job events and live tool start/end records with the registered analysis description. Fields include UTC timestamp, generated request/trace/span IDs, job ID, digested tenant ID, component, severity, sanitized error category and elapsed time. Client trace/request headers are ignored. Route templates replace arbitrary request paths. Questions, raw identifiers/events, model messages/replies, tool arguments, exception text, tokens and keys are excluded. Existing private scientific traces remain private; they are not monitoring exports. Docker rotates JSON logs at 10 MiB, keeping three files.

For a job trace, use the job ID printed by `ask_api.py`:

```powershell
.\.venv\Scripts\python.exe scripts\monitor_api.py --trace JOB_ID
```

`GET /api/v1/jobs/{job_id}/trace` requires the job owner. Request spans live in structured logs. The admission log links the HTTP request ID to the job ID; the job trace uses the job ID as its trace ID. The same saved request ID links admission, scheduling, worker execution, tool/LLM calls and persistence across processes. A separate span measures each provider attempt; logical LLM spans can include retries, validation, receipt reuse and checkpoint reconciliation, so they are not pure provider latency. Parent span IDs link nested worker operations to their execution attempt. Response spans measure preparation of server response headers, not network delivery to the client. A process killed mid-span leaves an open span; it is not a fabricated successful end. Old jobs have no retrospective trace. This is a documented local JSON tracing format, not OTLP/OpenTelemetry wire compatibility or an external tracing deployment.

Reading an old job can add response-only spans; `available` means records exist, not that its historical execution was traced. Inspect span names, limits and open IDs before treating a trace as complete. Each status/result request has its own request ID. Its job ID links it back to the investigation.

Each job's `telemetry.jsonl` sidecar stops appending at a 1 MiB threshold; simultaneous parent/worker appends can overshoot by a small record. Reads are strictly limited to 1 MiB. It never controls checkpoint identity, execution permission, recovery, result contents or billing. Failed writes do not repeat work or alter settlements. API-process write failures are counted; worker write failure counts cannot survive worker death, so missing/open/limited traces are additional coverage signals. The file can stop recording once full; `limit_reached` and open spans warn of incomplete evidence. Scientific artifacts and ledgers are never deleted to satisfy telemetry retention. The existing 5,000-job admission cap bounds sidecars to roughly 5 GiB worst case; disk-pressure alerts require operator action.

## Permissions

Existing credentials default to `operator: false`. Ordinary clients retain only owner-scoped traces. Global metrics and dashboards require an explicit operator client; possession of an ordinary bearer token does not grant access. The local deployment uses the existing `alice` operator account. For an already provisioned account:

```powershell
.\.venv\Scripts\python.exe scripts\set_api_operator.py --subject alice
docker compose up -d --no-build --force-recreate
```

The helper preserves the bearer token, records the previous private registry once, and preserves the existing file's ACL. It does not create a new account. Use `--disable` to revoke monitoring permission, then restart after confirming no active job. Do not replace a newer registry with the backup after other credentials have changed. Maintain the existing private directory ACL. Monitoring endpoints use the same body limits, subject/global rate limits, TLS, origin checks, no-store headers and local-only publication as other API endpoints.

## Measurement semantics

| Measurement | Source and bounds |
|---|---|
| API request totals and duration histogram | Process-local cumulative counts with fixed route/status labels; reset on restart. Server processing to headers, excludes socket body delivery. Current scrape is included in active requests but not completed totals yet. |
| API p50/p95/p99, rate and 5xx fraction | Exact order statistics over at most 2,048 completed requests in the last 300 seconds. Capacity truncation under sustained traffic is visible as `window_capacity`; the five-minute rate becomes a lower bound when saturated. No production availability inference from a local sample. |
| Queue/running/terminal states, recoveries, queue wait and creation-to-terminal duration | Existing durable API database, at most the retained 5,000 jobs. Queue wait is first start minus creation. Completion duration includes queue wait and interrupted/recovery time; cancelled/abstained/failed jobs remain distinguishable by state counts. |
| Tool success/failure and algorithm duration | Actual operation outcomes and matching top-level tool records' `elapsed_s`, newest 100 jobs, at most 1,000 operations each; ten-second cache. Nested records are excluded from the parent timing sum to avoid double counting. Timing includes the trusted tool's documented work/caching; it is not a kernel-only profiler. |
| Graph sizes | Numeric `active_nodes`/`unique_edges` in the saved graph record. Counts describe each recorded workflow input, not necessarily a saved research graph or every internal forecast graph. |
| Worker peak RSS | Linux process high-water RSS on worker spans, including imported libraries; shared process peak cannot be attributed independently to each algorithm. Unavailable measurements are null. Cgroup memory/PID usage/limits and free volume disk are separate readings. |
| LLM calls/tokens/retries/categories/reservation estimates/actual-or-assumed charge | Existing durable operation ledger over newest 100 jobs. These totals include mock and live runs: mock contributes tokens and zero cost. `provider`/`model` identify the configured live policy, not the identity of mock completions. Failed uncertain calls can retain assumed charges/token bounds, not confirmed provider usage. Pricing/HTTP 429 signals are observed without another provider request. |
| Structured-output failure | Durable `malformed` category from the existing receipt parser. Tool-selection failures include plan rejection spans and rejected tool operations. |
| LLM/provider timing | Actual newly instrumented spans. No historical timings are inferred from SQLite update timestamps. Logical calls may reuse receipts; provider-request spans exist only when `complete` is actually invoked, including deterministic mock calls. Pricing bootstrap requests are not included in completion timing. |
| Money | Durable API `charged_usd`, settled charges and reserved/held exposure are distinct. Retained project budget includes the original authorized prior-spend snapshot and new API holds/charges. Reservation estimates are upper bounds, not actual cost. Cost per successful live analysis uses settled completed live jobs only; failures/holds remain separately visible. |
| End-to-end completion | Completed jobs divided by all terminal jobs; abstentions, partials, cancellations and interruptions remain visible and are not silently counted as successful answers. |

Durable snapshot time/coverage, database read failures, missing traces and unsupported fields are visible. TTFT and generation throughput remain null because this interface is non-streaming. Rate-limit counts require the new typed HTTP status signal; old/fake replies lacking it cannot be classified retrospectively. Prometheus `recent_*` series are rolling gauge projections, including their cumulative distribution buckets: do not apply `rate()` to them. Use `rate(blackgrid_http_requests_total[5m])` and histogram quantiles only for process API counters/histograms. Job IDs, tenant IDs, prompts and arbitrary tool names never become metric labels.

## Alerts, objectives and runbooks

The snapshot/dashboard and `blackgrid_alert{name="..."}` expose advisory alerts. They send no external notification and never retry paid work. Rules: database/scheduler unavailable; queue at least six or oldest wait over 120 seconds; 5xx fraction over 5% with at least 20 recent requests; recent permanent/transient/uncertain provider failures; retained budget at 80%; sampled worker peak RSS over 1.5 GiB; free disk below 1 GiB; telemetry write/read failures. Provider/memory rules use the newest-100-job sample and may remain firing for historical failures until they leave the window. They are review signals, not new incidents on every refresh.

Measured baseline and acceptance are in [Phase 5 evidence](production_phase5/report.md). Initial local objectives are readiness client p95 below 3 seconds and this fixed offline question completing within 180 seconds on the current 1 CPU/2 GiB service. These are provisional engineering objectives derived from the baseline, not validated production SLOs or a latency optimization claim. Failure/availability SLOs require Phase 6 workload measurements over time; no fabricated 99.9% uptime claim is made. Keep separate objectives for live providers and each tool family before increasing capacity.

1. **5xx/storage/scheduler:** check `/health/ready`, Docker health and free disk. Preserve the volume, job IDs and ledgers. Inspect sanitized error categories and open traces. Stop new submissions if the scheduler is unavailable. Review any active live job before restarting; never delete the database or restore an old ledger over current spend.
2. **Queue/tool slowness:** inspect queue wait, tool-duration totals and graph counts. Compare the same family/input/mode. Current worker admission is one active plus eight waiting. Increasing concurrency/resources requires measured evidence; no automatic scale-up is configured.
3. **Provider/schema/429:** inspect error categories, typed rate-limit signals, logical-call versus provider timing, token usage and budget holds. Existing retry/backoff and uncertain-call reconciliation remain authoritative. TTFT cannot be diagnosed from this interface. Do not replay an uncertain paid request with a new idempotency key.
4. **Cost pressure:** compare settled charges, held exposure and retained project ceiling. Costs of failed runs remain charged/held as appropriate. Do not change authorization, pricing or caps just to clear an alert. A historical hold needs explicit reconciliation.
5. **Resource pressure:** compare worker RSS against container memory usage/limits, disk-free and PID readings. Check Docker resource status for CPU/OOM details not attributed by these spans. Stop unneeded submissions and inspect the slowest tool. Preserve raw inputs and authoritative run evidence.
6. **Missing/limited traces:** old jobs have no sidecar. New missing/open/limited records require checking filesystem permissions, the 1 MiB cap and worker termination. Treat trace completeness separately from scientific completion. Regenerating telemetry never authorizes rerunning an analysis.
7. **Rollback:** wait for an idle service; restore Compose image tag `blackgrid:phase4-tools` and its previous logging configuration if needed. Remove `operator` fields from the credential registry for the old strict schema, preserving subjects/digests and any newer accounts. Recreate the same service with the same current volume. Keep sidecars; they are ignored by the old service except a pre-checkpoint recovery folder may need review. Do not restore old `jobs.sqlite` or billing snapshots. Failed/uncertain live runs need review before any recovery.

Grafana and OpenTelemetry exporters remain unnecessary for this one-service workload: the existing authenticated API hosts real metrics/dashboard/traces. The local schema and Prometheus endpoint provide a later integration boundary; an external collector, credential disclosure or tracing upload needs separate review/authorization.
