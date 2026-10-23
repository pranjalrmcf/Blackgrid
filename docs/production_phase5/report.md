# Phase 5 — observability, monitoring and LLMOps

Status: complete for the documented local single-host scope, 23 October 2026. Phase 6 remains unapproved.

## Existing state and smallest change

The cumulative Phase 4 service already has a persistent bounded queue, private operation receipts/costs, safe mock recovery and automatic routing across all 18 tools. It exposes sanitized progress but has no HTTP metrics, operational trace endpoint, monitoring page or alert evaluation. No separate monitoring stack is running.

The smallest change adds two local modules (`operations/telemetry.py` and `operations/monitoring.py`), thin API/job/engine wrappers and a typed HTTP 429 signal in the existing transport. The existing service serves authenticated aggregate monitoring and owner-scoped traces; command-line helpers use existing tokens and TLS. No numerical method, planning prompt, provider model, tool selection, LLM call sequence, budget policy or experimental protocol is altered. The original live/provider retry/reconciliation logic stays authoritative. Earlier dirty Phase 4 work and saved negative results are preserved.

Complexity is moderate because context crosses the API/dispatcher/contained-worker boundary and monitoring must not disclose private state or affect recovery. Main risks are trace I/O overhead, missing spans after process death, metric cardinality, tenant disclosure and confusion between actual charges and holds. Controls are fixed names/route labels, independent capped sidecars, no raw payload/exception export, explicit operator authorization, read-only aggregate ledger queries and clear sampling/accounting semantics. A `telemetry.jsonl` sidecar is permitted among pre-checkpoint recovery files; it cannot create a second scientific run or waive checkpoint validation.

Resource plan: retain the existing 1 CPU, 2 GiB, 128-process service; no new dependency or service. Offline tests use identical limits, network disabled and read-only source/data/root. Each private trace is capped at 1 MiB, API request samples at 2,048, workflow metric scans at newest 100 jobs/1,000 operations per job and cached for ten seconds. Docker stdout rotates at three 10 MiB files. Existing job admission remains capped at 5,000. No automatic retention deletes scientific evidence or spend.

Conditional technologies: a separate Grafana/Prometheus server and OpenTelemetry collector/exporter are unnecessary at this workload. The existing service supplies a server-rendered operator dashboard, Prometheus-compatible text and a documented local cross-process JSON span format. No OTLP compatibility, external telemetry backend, production load validation or distributed multi-host execution is claimed. See [measurements, permissions, alerts, objectives and rollback](../monitoring.md).

## Executed checks and evidence

- Existing API regression on Windows: 25 passed, two Linux-specific skips, 9.42 seconds.
- Initial combined Windows run: one new monitoring assertion inspected a deliberately cached snapshot immediately after submission; 46 passed and seven skipped. Its fixture now explicitly expires the ten-second cache before asserting new durable state. No monitoring cache or scientific behavior was changed to satisfy the assertion.
- Linux focused monitoring/fake-provider/recovery suite: 37 passed in 89.68 seconds, with network disabled and 1 CPU/2 GiB/128-process/read-only-root controls. It verified operator-only aggregates, owner-only traces, no arbitrary path/header/question/model payload in logs/labels, bounded/corrupt trace reads, write-failure isolation, known histogram/alert answers, durable holds, database failure visibility and actual cross-process worker/token/cost/parent-span linkage using fixture-only provider responses.
- The original running Phase 4 service baseline used 30 HTTPS readiness probes and one explicit mock community question: client p50 2.0601 seconds, p95 2.0929 seconds, p99 2.1014 seconds; question wall time 93.4060 seconds. See [baseline](baseline.json). These are local client observations, not server-only duration or production percentiles. No external model/pricing request was made.

The first full Linux run passed 635 tests in 389.81 seconds. Review then isolated durable-monitor scan locking from API counters and removed dispatcher-state mutation from monitoring reads, adding regressions and correlating response fetches with job traces. The following full image run passed 637 tests in 362.59 seconds; its log/XML are retained as `regression_pre_timing_fix.*`.

Review of actual dashboard records then found that a sensitivity operation contains nested community-test records as well as its own inclusive elapsed time. Summing all records attributed nested work twice to sensitivity. Monitoring now selects only the matching top-level tool's elapsed record, with a known-answer 3-second nested/5-second parent fixture asserting a 5-second parent measurement. All 11 monitoring checks passed in 11.44 seconds. The scientific operation records and their calculations were not edited. Earlier acceptance/monitoring/trace snapshots are retained as `*_pre_timing_fix.json` so the display correction is explicit.

The final test image passed **638 tests, zero skips, in 357.23 seconds**, with network disabled, read-only root/data and 1 CPU/2 GiB/128-process limits. See [the full log](regression.log) and [JUnit evidence](regression.xml). Counts from successive runs overlap; they are not additive. The final image includes the known-answer nested-timing test and all 18 tools exercised through contained workers with fake provider responses.

## Deployed acceptance

The cumulative **`blackgrid:phase5`** image is running in the existing `blackgrid-blackgrid-1` service with the original `blackgrid_blackgrid-state` volume. Final image ID: `sha256:9768cb44329f1608cff3fab7554e2b93b803230026ec2736f2b97af742e5c3fb`. All **77 Python source files** exactly matched the running image. UID 10001, read-only root, read-only data/evidence/secret binds, localhost-only TLS port, dropped capabilities, no-new-privileges and the original 1 CPU/2 GiB/128-process limits were verified. JSON log rotation is three 10 MiB files. See [runtime verification](runtime_verification.json) and [source manifest](source_manifest.json).

A private SQLite backup was made inside the volume before replacement: `jobs-pre-phase5-20261023T063210Z.sqlite`. All original **23 job rows**, including their private request envelopes, identity, states and money fields, matched exactly after the final deployment; only their combined SHA-256 is exported. The existing token was preserved while `alice` received explicit monitoring permission; the previous registry remains private in `.secrets/clients.pre-phase5.json`. The final service has 25 jobs: 21 completed, three cancelled, one preserved earlier partial, none active. API charged spend remains **USD 0.003936626**; this does not include the policy's separately retained prior-spend snapshot. See [pre-deploy record](pre_deploy.json) and [final ledger verification](ledger_verification.json). No older ledger was restored over current spend.

The final acceptance submitted the same fixed question in explicit mock mode, then compared the complete minimized API result with the Phase 4 baseline. Results matched exactly, including numerical findings, scopes, conclusions, tools, call/token counts and zero mock cost. Scheduling, execution, LLM/provider calls, tools, persistence and response spans were present with no open spans at the completed-job check. Authenticated Prometheus text, JSON and HTML dashboard used actual records. See [acceptance](acceptance.json), [trace](trace.json), [metrics](metrics.prom), [snapshot](monitoring.json) and [dashboard](dashboard.html).

| Local observation | Phase 4 baseline | Final Phase 5 |
|---|---:|---:|
| HTTPS readiness client samples | 30 | 30 |
| Client p50 seconds | 2.0601 | 2.0635 |
| Client p95 seconds | 2.0929 | 2.0791 |
| Client p99 seconds | 2.1014 | 2.1026 |
| Fixed offline question wall seconds | 93.4060 | 93.2672 |

Both runs meet provisional local objectives of readiness client p95 below three seconds and this fixed mock question below 180 seconds. A single before/after job and small transport-inclusive samples do not establish an optimization or production SLO. No latency improvement is claimed. Phase 5 adds measurement; controlled performance workloads belong to later approved work.

Actual operation records identify sensitivity as the dominant cost in the sampled community workflow: eleven inclusive sensitivity timings total 695.1344 seconds (about 63.19 seconds per operation), versus eleven community-test timings totaling 181.3547 seconds (about 16.49 each). A historical forecast timing is 110.6931 seconds but has a different full-history scope and only one sample, so it is not compared as equivalent work. Sampled graph records contain 104 active nodes and 137 edges. The newly traced worker peak RSS is 216,154,112 bytes (about 206 MiB), a process peak including imported libraries rather than per-algorithm allocation. These are diagnostics, not new scientific or scalability claims.

The final service was restarted while idle. The completed result remained exact and the previously saved trace prefix remained unchanged. Actual command logs contained the tool and registered analysis description and request/job correlation, and did not contain the known bearer token, provider key or TLS private key. All eighteen tools remained available. The first immediate restart probe raced listener startup; the read-only helper now waits for readiness with a bounded retry loop, without resubmitting any job. See [restart/log verification](restart_verification.json). Docker log rotation/recreation can remove request logs; private job sidecars persist in the volume, with their documented size/coverage limits.

Resource use: three explicit offline mock acceptance/baseline jobs, fixture/synthetic regression runs and local cached image builds. **Zero paid calls, zero real pricing requests, zero external telemetry exports, zero new infrastructure services and no new dependencies.** Existing scientific data, model settings, budget limits, negative results, checkpoint receipts and held-out evidence were preserved. No GitHub commit/push or Phase 6 work was performed in this phase.

## Scientific and operational limits

Observability does not expand scientific validity. CollegeMsg findings remain descriptive for the configured graph; saved synthetic research remains separate; forecast rankings are not calibrated probabilities. Negative results, earlier partial jobs and uncertain paid holds remain recorded. No new paid execution is authorized by monitoring.

The next smallest task after acceptance is an explicitly approved Phase 6 bounded synthetic workload/virtual-user protocol. Phase 6 is not started by this work.
