# Phase 6 execution report

Completed 23 October 2026 for the bounded single-host, synthetic/mock scope. The cumulative `blackgrid:phase6` image is deployed in the existing service and contains all earlier tools, security, reliability and monitoring work. vLLM is explicitly out of scope. Phase 7 remains unapproved.

## Implemented

The existing API now serves an automatically refreshing operator dashboard, with local charts, five-second polling, bounded history, stale/disconnected states, tool timings, alerts and the latest sanitized benchmark stage. Secure, HttpOnly, SameSite=Strict, path-scoped cookies expire after 15 minutes. Same-origin checks protect state changes, operator permission is checked on reads, and the dashboard cookie cannot authorize job APIs. No external telemetry, assets, credentials in URLs/local storage or additional production service is introduced. See [the operator guide](guide.md).

The optional Locust benchmark image and isolated target use fresh private credentials and a separate retained state volume. The target has no real-data, live-policy, provider-key, prediction/research-evidence or generator-truth mount. All 15 independently generated cases use five families at 100/300/1,000 requested nodes; actual active nodes/edges, hashes and seeds are recorded. Direct graph timings cover profile/centrality on all 15 cases. API/mixed stages use only the registered 100-node stochastic-block case. Synthetic budgets are explicit and do not replace real-data configurations. Planted membership and temporal future events stay outside runtime mounts/prompts.

The synthetic adapter marks only manifest/checksum-verified event sources as synthetic. A narrow behavior-factory adapter binds those actual events when the graph's real-data source is intentionally absent. It neither reconstructs events from graph topology nor changes existing real-data handling, tools, prompts, scientific thresholds or paid limits. Regression checks exercise both actual contained synthetic centrality and behavioral jobs.

## Protocol history and preserved failures

The frozen [v1 protocol](../../protocols/production_phase6_v1.json) preceded execution. The first launch, `20261023T072948Z-24554c`, failed because a Compose tmpfs flow-list entry was parsed as two entries; its evidence is retained. After quoting that entry, v1 pilot `20261023T073148Z-2d5255` completed all stages, but 4 of 27 accepted jobs were partial. The behavioral tools correctly refused an unbound synthetic event source. The direct mock fixture also exercised only the shortest latency rather than all three declared latency values.

These findings were inspected before registering [v2](../../protocols/production_phase6_v2.json). It records both corrections and prior inspection. Seeds, workload questions/weights, graph budgets, concurrency, durations and stopping thresholds were unchanged. The v1 protocol, reports, raw timings, partial outcomes and durable volume remain retained. v2 is a benchmark protocol revision, not an application version that omits previous phases. Do not interpret the two pilots as a controlled performance improvement comparison.

## Executed v2 measurements

Attempt [`20261023T074841Z-3b55c5`](../../results/production_phase6/20261023T074841Z-3b55c5/reconciliation.json) completed in 241.42 seconds. Independent reconciliation recomputed request/route percentiles from raw samples, checked admission counts, actual virtual-user peaks and every accepted job's state/timestamps against the durable ledger. All 27 accepted workflows completed with verified aggregate results. Six submissions were explicitly rejected when the bounded queue was full. There were no unexpected HTTP failures, rate-limit responses or censored jobs. The 30 direct graph tool samples completed. Mock fixtures exercised three explicit delays and malformed JSON plus transient/permanent/uncertain fake error classes; these are fixture detection checks, not end-to-end provider retry benchmarks.

| Workload | Users | HTTP samples | Accepted / completed | Rejected | API p95 (ms) | Queue p95 (s) | Creation-to-terminal p95 (s) | Completed/minute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Capabilities API | 1 | 5 | 0 / 0 | 0 | 22.36 | — | — | — |
| Capabilities API | 5 | 28 | 0 / 0 | 0 | 33.90 | — | — | — |
| Capabilities API | 10 | 53 | 0 / 0 | 0 | 66.55 | — | — | — |
| Mixed mock workflow | 1 | 16 | 4 / 4 | 0 | 865.86 | 0.0098 | 5.05 | 6.59 |
| Mixed mock workflow | 5 | 76 | 9 / 9 | 0 | 61.48 | 22.03 | 26.87 | 10.69 |
| Mixed mock workflow | 10 | 183 | 14 / 14 | 6 | 71.14 | 38.88 | 44.35 | 11.51 |

Counts include drain; completed/minute uses total elapsed stage time, not just the offering interval. Percentiles use nearest rank. In small samples, a single slow response can determine p95/p99; the single-user API p95 includes the observed 865.86 ms response and is not omitted as an outlier. Every route's p50/p95/p99, job queue/worker/terminal distributions and raw request/resource samples are saved, with [CSV comparison](../../results/production_phase6/20261023T074841Z-3b55c5/stages.csv).

The target was limited to 1 CPU, 2 GiB and 128 PIDs; it retained one active worker/eight queue slots. The separate generator was limited to 0.5 CPU/512 MiB/128 PIDs. Observed target peak memory in the ten-user mixed stage was 337,645,568 bytes; generator peak RSS was 57,208,832 bytes and CPU time 1.47 seconds. Raw CPU/memory series are retained. Benchmark numerical threads are set to one explicitly, unlike unchanged normal production defaults. Observer polling overhead is included in target use; generator CPU/RSS is measured separately. Dashboard polling overhead was not isolated in an A/B experiment.

Docker reported 22 CPUs and 16,591,138,816 bytes of memory available to its Linux engine, x86-64, WSL kernel `6.6.114.1-microsoft-standard-WSL2`, Docker 29.5.2. These are engine resources, not a claim that the target had them all. The host was not dedicated: offline regression/deployment verification also ran under separate limits. Locust 2.46.6, NetworkX 3.6.1, NumPy 2.4.6 and SciPy 1.17.1 are recorded with source hashes, dirty HEAD `9c10ce62a58b80aca1cac8bc52a44e11da58eb35` and immutable image identity in each attempt.

## Verification and deployment

- The clean test image ran the full offline suite: **647 passed, 2 skipped**, in 378.86 seconds. The skipped tests require the private CollegeMsg input, which is absent from the image. Both then ran with only the existing read-only CollegeMsg mount: **2 passed** in 4.44 seconds. Thus all 649 collected checks were executed successfully across those runs. [Full output](evidence/regression.log), [JUnit](evidence/regression.xml), [mounted-data output](evidence/real_data_checks.log), [JUnit](evidence/real_data_checks.xml).
- The correction's focused Linux checks passed **19 tests** before the final image/pilot. Earlier regression evidence is retained as `regression_pre_synthetic_event_fix.*`.
- Real headless Edge verified login, automatic updates, cleared credential input, mobile overflow, sign-out revocation and zero page errors/external page requests. Node independently verified TLS and the launcher's certificate public-key pin. No credential/browser-storage/HAR exports were produced. [Evidence](evidence/browser_verification.json), [desktop](evidence/dashboard-desktop.png), [mobile](evidence/dashboard-mobile.png).
- The deployed image's **84 source/asset files exactly match** local content. UID 10001, read-only root/binds, dropped capabilities, no-new-privileges, 1 CPU/2 GiB/128 PIDs, bounded logs, localhost HTTPS and the original `blackgrid_blackgrid-state` volume were verified. Locust, pytest and vLLM are absent from production. [Deployment evidence](evidence/deployment_verification.json), [source hashes](evidence/source_manifest.json).
- One explicitly mock job returned the exact complete minimized API result from the unchanged Phase 5 baseline. Result and trace survived service restart, all 18 tools remain available, **all columns of the original 25 job rows remain exact**, and API charged spend remains **$0.003936626**. No old spending ledger was restored. The pre-deployment database backup remains inside the original volume. [Parity result](evidence/parity_result.json), [pre-deployment metadata](evidence/pre_deploy.json).

The deployed image is `sha256:a6bcbeb044cdb2bf56d39edb473563785cb15d9333264839e65be17101ad018e`. Retain `blackgrid:phase5` for rollback with the current state volume; never overwrite newer billing records with the pre-phase snapshot. Source remains uncommitted pending a separate user request.

## Cost, limits and next task

New real provider calls: **0**. New provider spend: **$0**. Local Docker CPU, memory, disk and dependency/image downloads were used; no cloud/GPU service was provisioned. All benchmark attempts/volumes are retained. The production service is ready after restart; the isolated benchmark target is stopped.

These short, exploratory closed-loop synthetic/mock results measure engineering behavior, not real LLM inference, quality, calibrated scientific efficacy, real-world validity, sustained capacity or production availability. The single active worker is the observed queue bottleneck; ten concurrent clients do not imply ten parallel analyses. Queue rejection remains explicit. No latency improvement, 1,000-user support or 99.9% uptime is claimed. Future optimization needs a dedicated, longer controlled baseline and explicit acceptance targets. vLLM is not included.

The next smallest task, after separate approval, is Phase 7's bounded resilience/security and consistent restore verification. No Phase 7 work has started.
