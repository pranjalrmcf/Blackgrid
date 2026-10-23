# Final benchmark — bounded synthetic/mock repeat

Attempt [`20261023T113117Z-ea5a8f`](benchmark/20261023T113117Z-ea5a8f/reconciliation.json) repeated the unchanged [Phase 6 v2 workload](../../protocols/production_phase6_v2.json) under the pre-execution [Phase 9 protocol](../../protocols/production_phase9_v1.json), on the cumulative Phase 9 production image with owner-scoped tool caching enabled and fresh isolated state. Prior Phase 6/8 outcomes had been inspected; this is exploratory engineering verification, not a confirmatory improvement comparison. No workload/budget/threshold was tuned after these results.

The run lasted **240.25 seconds**. All **26 accepted jobs completed**, with verified aggregate results. Seven submissions were explicitly rejected by the bounded queue. No unexpected HTTP errors, failed/partial/censored jobs or real-provider calls occurred. Thirty direct graph-tool samples covered 15 generated cases across five families and requested sizes 100/300/1,000; the API/mixed stages used only the registered stochastic-block 100-node case. Manifests record actual active nodes/edges, hashes and seeds. Planted labels and future events were outside runtime mounts/prompts. Mock response delays/errors are scripted fixtures, not real-model inference measurements.

| Workload | Users | HTTP requests | Accepted/completed | Queue rejections | API p95 / p99 ms | Queue p95 s | Creation-to-terminal p95 s | Completed/min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Capabilities | 1 | 5 | 0/0 | 0 | 39.76 / 39.76 | — | — | — |
| Capabilities | 5 | 28 | 0/0 | 0 | 69.99 / 73.08 | — | — | — |
| Capabilities | 10 | 53 | 0/0 | 0 | 69.29 / 72.00 | — | — | — |
| Mixed workflow | 1 | 16 | 4/4 | 0 | 855.34 / 855.34 | 0.0176 | 5.28 | 6.58 |
| Mixed workflow | 5 | 77 | 9/9 | 0 | 55.56 / 78.81 | 22.42 | 27.47 | 10.68 |
| Mixed workflow | 10 | 174 | 13/13 | 7 | 81.19 / 178.10 | 40.73 | 45.58 | 11.33 |

The one-user mixed p95 includes its observed slow request; it is not removed as an outlier. Nearest-rank p50/p95/p99, per-route distributions, HTTP throughput, queue/worker/terminal latencies, raw resource series, token counts and every accepted job's ledger state are retained in each stage. Completed/minute includes drain time; request throughput is requests divided by full stage elapsed time. This is a short closed-loop pilot with small samples and one worker, not sustained or open-loop capacity. Different completion counts from Phase 6 do not establish a speed or capacity improvement.

Target controls: 1 CPU, 2 GiB, 128 PIDs, one worker/eight queued, one numerical thread for this benchmark. Separate generator: 0.5 CPU/512 MiB/128 PIDs. Target peak observed memory in the ten-user mixed stage was **388,317,184 bytes**; generator peak RSS **59,056,128 bytes**, CPU **1.399 seconds**. Raw CPU/memory samples are in `resource_series.json`; generator measurements are separate from target cgroup readings. The WSL2 Docker engine exposed 22 CPUs and 16,591,138,816 bytes, x86-64, kernel 6.6.114.1-microsoft-standard-WSL2, Docker 29.5.2. The host was not dedicated; other bounded verification ran alongside parts of the workload.

Independent reconciliation recomputed percentiles from raw request samples and matched all 26 jobs/timestamps/attempts/costs to the durable ledger. [Raw attempt](benchmark/20261023T113117Z-ea5a8f/attempt.json), [CSV](benchmark/20261023T113117Z-ea5a8f/stages.csv), [reconciliation](benchmark/20261023T113117Z-ea5a8f/reconciliation.json). Actual provider cost **$0**, real calls **0**. Image identity and source hashes are recorded; measurements were made on the working tree based on `20b6976`, before the Phase 9 commit.

Recovery and production rollback have separate evidence under [evidence](evidence/); they are not combined into job latency statistics. The earlier [Phase 8 controlled cache comparison](../production_phase8/report.md) remains the evidence for its approximately 35% warm-cache median improvement, with no cold improvement claim. This final repeat does not establish 99.9% availability, production SLO compliance, real-provider latency, ten parallel analyses or unbounded scalability.
