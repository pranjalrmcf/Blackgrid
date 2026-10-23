# Phase 8: measured repeated-work optimization

Completed 23 October 2026 for the documented single-host scope. Cumulative **`blackgrid:phase8`** is deployed with optional verified deterministic graph-tool reuse enabled. All earlier tools, reliability/security controls, scientific settings and LLM workflow remain. vLLM, paid testing, new infrastructure and Phase 9 were excluded.

## Bottlenecks and smallest change

Phase 6 v2 measured ten mixed users with 38.88 s p95 queue wait and 44.35 s creation-to-terminal p95 on one worker; 14 jobs completed and six queue-full submissions remained explicit. Production's accumulated tool timings also identified community/sensitivity work as expensive. These prior results were inspected before registering a separate [Phase 8 protocol](../../protocols/production_phase8_v1.json); they were not rewritten.

The fresh CPU diagnostic on the pinned synthetic fixture attributed most graph-path time to existing edge swapping and Louvain/community work: `double_edge_swap` accumulated 1.139 s of a 1.700 s instrumented graph run; `best_modularity` accumulated 0.520 s. Inclusive function times overlap and must not be added. That diagnostic used 19 primary and 19 sensitivity nulls, one restart and one sensitivity replicate. API comparisons retained the saved configuration and existing 99-null sensitivity path. The profile is explanatory, not a before/after sample. [Raw profile](profile_baseline.json), [profiling script](../../scripts/profile_phase8.py).

The API previously forced `--no-cache` for every job/resume despite already having a validated deterministic cache. The change enables that existing mechanism through a small API policy wrapper: authenticated owner/mode/config and source/dependency/runtime namespaces, bounded private retention, ordinary graph/data verification and normal tool prerequisite validation. No analytical algorithm, seed, precision, null/restart/sensitivity count, prompt, model, planning rule or provider-call sequence changed.

Cache I/O is disposable: malformed/oversized/link entries are rejected, atomic temporary writes replace validated envelopes, and storage/retention failures fall back to computation. Progress/command logs explicitly identify verified hits. Behavioral, forecasting and research branches remain uncached. The optimization never caches a model reply or bypasses pricing/budget accounting. See [operation, retention and rollback](guide.md) and [initial scope](design.md).

## Registered same-input comparison

Both images used identical checksum-pinned, independently generated inputs, saved numerical settings, fake credentials, authenticated API routes, offline mock provider and 1 CPU/2 GiB/128 PID limits. The requested 100-node stochastic-block fixture has **98 active nodes/196 edges** after the existing event projection. No raw real dataset, held-out truth, live policy or provider key was mounted.

Three baseline uncached jobs ran in immutable Phase 7. The Phase 8 candidate ran three cold jobs under separate fresh owner namespaces, one separately reported prime job and three warm jobs for the primed owner: **ten total jobs**. Scientific fingerprints, complete minimized API results and LLM call/token/cost counters matched for every job. All made one mock planner call; no model response was reused. [Independent reconciliation and raw samples](comparison-v1/summary.json), [baseline](comparison-v1/baseline.json), [candidate](comparison-v1/candidate.json).

| Condition | Timed jobs | Median creation-to-terminal | Cache hits/job |
|---|---:|---:|---:|
| Phase 7 uncached | 3 | **6.886977 s** | 0 |
| Phase 8 cold cache | 3 | **6.887511 s** | 0 |
| Phase 8 warm cache | 3 | **4.447181 s** | 3 |

The warm median was **35.43% lower** than the uncached median. There was no observed cold-speed improvement; the median difference was approximately 0.0005 s and the sample is too small to establish an overhead bound. The prime job took 6.481511 s and is not included in the warm median. There is no confidence interval, statistical significance, sustained-load SLO or real-provider speed claim.

Top-level tool span totals in the baseline samples were 1.918–2.322 s; warm hits took 0.0020–0.0027 s. This is reuse instead of recomputation, not a faster graph algorithm. Much of the warm job's remaining roughly 4.45 s is workflow/startup/storage overhead. It is an unattributed timing residual; import time and individual SQL queries were not separately measured. Mock LLM/provider, artifact, workflow and API route timing samples are separately retained in the reconciliation. Nested span categories must not be summed as independent costs. Maximum observed job-span process RSS was about 221 MB; no memory reduction is claimed.

The comparison used a sequential ASGI client rather than external TLS requests and only three timed samples per condition. The host was not dedicated; a separately limited regression container ran during the candidate. Benchmark CPU quotas are enforced, but precise isolated CPU utilization and real-provider latency/quality were not measured. The recorded graph profile, span decomposition and prior Phase 6 resource series support the bottleneck assessment without inventing those missing measurements.

## Deployed configured-graph demonstration

The existing service was updated only after an idle check and a private offline full backup: **786 files/18,431,581 bytes**, completed in **55.29 s**. The same state volume, registry, TLS, live grant and reviewed data/evidence bindings were retained. [Backup metadata](evidence/production_backup.json), [pre-deployment ledger identity](evidence/pre_deploy.json).

One free cold mock request on the unchanged configured observed graph completed in **87.019882 s** creation-to-terminal. After service restart, the same question as a new job completed in **5.138431 s**, with all three graph tools reporting verified cache hits. Both complete minimized results exactly matched the unchanged Phase 5 scientific baseline, including token/call counters. This is **one demonstration pair**, not the replicated synthetic benchmark. Client-observed helper times were 91.0 s cold and 11.281 s warm; those include different polling intervals and request overhead, so the database timestamps are reported separately. [Runtime/parity verification](evidence/deployment_verification.json), [cold result](evidence/parity_result.json), [warm result](evidence/warm_parity_result.json).

All columns of the **37 existing job rows** remained exact. API charged spend remained **$0.015085346000000001**, entirely retained prior spend. No earlier ledger was restored over current accounting. Two new explicitly mock jobs were submitted, with **zero external provider calls and $0 new provider spend**. Cache persistence after restart, original result/trace persistence and availability of all 18 tools passed.

The deployed image is **`sha256:23c46e481309677bb6573915e0a1a6d58cd3b75950f520be8cf575c42f2e452f`**. Its 86 source/asset files match the local source exactly and its application source hashes match the measured candidate. UID 10001, read-only root/binds, dropped capabilities/no-new-privileges, localhost HTTPS, original volume, bounded logs, 1 CPU/2 GiB/128 PIDs and absence of pytest/Locust/vLLM in production were verified. [Source/runtime evidence](evidence/deployment_verification.json).

## Regression, security and scaling limits

The full offline Linux image suite passed **674 tests**, zero failures/skips, in **392.79 s**, including the read-only existing-data checks. An additional fake-provider live-cache integration check passed separately in **13.91 s** on the same application image with the updated test mounted read-only: **675 executed checks total**. It verified two cold/warm jobs still made `GET, POST, GET, POST` broker calls, each retained one LLM call and settled its artificial charge exactly. These fake fixture charges are not real provider spend. [Full suite](regression.log), [JUnit](regression.xml), [live-cache check](live_cache.log), [JUnit](live_cache.xml).

Cache-specific checks cover owner/mode/config/code invalidation, retention/age limits including quarantine/temp entries, oversized-cache rejection, cache-write failure fallback, real contained owner-scoped cold/warm API parity and paid-accounting preservation. The existing scientific, invalid-tool/method, leakage, missing-edge, artifact, budget, retry, recovery, cancellation, tenant/origin and network-containment checks passed too.

The exact final image was scanned with the existing pinned Trivy 0.76.0/public database. It retains **zero critical findings and zero Python findings**, alongside **44 high, 58 medium, 61 low and one unknown OS finding instance** without available distribution fixes. None were suppressed. These are the same residual risks documented in Phase 7, not a vulnerability-free or public-release approval. No image/private-state upload or Docker socket was supplied to the scanner. [Exact scan identity and findings](evidence/scan_summary.json).

The live dashboard passed browser login, live updates, local certificate-pin verification, desktop/mobile rendering and sign-out revocation, with zero page errors/external page requests and no credential/storage/HAR export. [Browser evidence](evidence/browser_verification.json).

One active worker/eight waiting jobs remain. Repeated eligible work can release that worker sooner; new graphs, misses and uncached tool families retain their original computation. No ten-user capacity improvement was measured in this sequential comparison, and Phase 6 saturation is not erased. A second writer on the same state store remains lease-rejected. Multiple worker replicas would require a supported admission/accounting/artifact-ownership design and a new controlled workload; Kubernetes is not justified by the measured single-host scope. No CPU/memory allocation or provider concurrency was raised.

Verification records the Phase 8 working tree based on the prior `6f5631a` main commit; the user subsequently authorized committing and pushing Phase 8 to main. Existing local planning documents remain Git-ignored. Next smallest task, after separate approval, is Phase 9 reproducible CI/release gates while retaining residual security findings and these performance limits. No Phase 9 work has begun.
