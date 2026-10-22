# Phase 3 — Authenticated API and access boundaries

22 October 2026. Status: **implemented and verified for the bounded single-host offline API**. Phase 4 remains unapproved. Existing work was first pushed as commit `594e91b`; Phase 3 is a separate reviewable change. The running Phase 2 Compose service was not replaced.

Subsequent user authorization connected the API to the existing Compose service. It now uses the same state volume at localhost HTTPS, with read-only credentials/certificate mounts and network-denied Linux workers. The original verification narrative below describes initial Phase 3 delivery; see the [subsequent service integration report](service_integration/report.md) for current runtime state and checks.

The user then identified the missing live LLM capability and authorized its integration, reserving the first real test call for themselves. The retained-authorized live workflow is now wired through a restricted provider broker, with historical accounting and progress reporting. See [live integration verification and limits](live_integration/report.md). No paid request was issued during implementation.

## Changes and acceptance

The [pre-implementation design](../phase3_api_design.md) records the interface audit and smallest acceptance slice. The [operator/API contract](../api.md) documents routes, schemas, identity, provisioning, limits, failures, transport and compatibility. FastAPI/Uvicorn provide a separate opt-in listener; the legacy console is not exposed through it.

Added authenticated `/api/v1/jobs` submission/status/results/cancel and allowlisted aggregate artifact download, an authenticated OpenAPI schema, plus local health routes. Opaque bearer credentials are provisioned outside source/image layers and stored as digests. All owner-dependent reads/writes require authenticated identity; other-owner and missing jobs return indistinguishable 404 responses. Each job has a private subject namespace and generated directory. No client path/dataset/upload parameter is accepted.

Added bounded JSON parsing, duplicate-field/framing rejection, existing typed graph/config limits, stable errors/correlation IDs, origin/host controls, secure headers, per-subject and global rate buckets, one-job admission and bounded connection settings. Persistent SQLite submission metadata makes duplicate/conflicting submission behavior deterministic across threads and restart. An exclusive process lease prevents multiple API processes sharing this state. Interrupted jobs are retained without automatic replay. Cancellation uses the existing authoritative workflow flag; no force-unlock is exposed.

New API jobs execute the same fixed CLI workflow with mock mode, community family, first-window scope and reviewed data/config. Child environment excludes inherited credentials; stdout/stderr are suppressed instead of disclosing raw failures to HTTP clients. Scientific kernels, prompts/models, planner/critic decisions and existing workflow implementation were not changed in this phase. Operator source/config/data remain trusted; subprocess execution is not represented as a security sandbox.

## Dependencies and security repair

Added FastAPI 0.142.2, Uvicorn 0.54.0 and their required transitives. Initial lock comparison showed no existing version changes. The subsequent runtime audit found a critical pre-existing certifi certificate trust-store advisory, [GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2). Updated **only certifi 2026.7.22 → 2026.10.19** among existing packages. A documented package-specific publication-date exception preserves the general dependency freeze and numerical versions. The before-scan finding remains in `dependency_audit_before.json`; the final audit checked 58 runtime packages and reported **zero known vulnerabilities** in `dependency_audit.json`. This is a dated package advisory check, not an OS image scan or security certification.

## Executed verification

| Check | Actual result | Evidence |
|---|---|---|
| Windows API + legacy console/deployment checks | 54 passed, 1 skipped in 15.19 s; Windows cannot create the symlink fixture without extra privilege | `focused_tests.log` |
| Complete Linux offline regression | **574 passed in 224.68 s**, zero failures/errors/skips | `container_tests.log` |
| Production and test Docker builds | Both completed successfully, tags `blackgrid:phase3` and `blackgrid:phase3-test` | `production_build.log`, `test_build.log` |
| Actual Uvicorn listener over HTTPS | Validated temporary local certificate, HSTS, 401 without auth, 404 across owners, readiness 200, tiny real workflow correctly abstained, original job replayed after a process restart | `server_smoke.json` |
| Runtime dependency audit after targeted fix | 58 packages; no known vulnerabilities | `dependency_audit.json` |

API regressions cover authentication, all owner-dependent routes, schema/body/framing rejection, legacy-route exclusion, rate buckets, simultaneous identical submissions, conflicting retries, restart/interruption identity, process lease, traversal/symlinks, minimized result download, changed configuration rejection, existing cancellation flag, external-bind TLS requirement and a real tiny offline workflow. Linux exercised the symlink case skipped on Windows. Tiny fixture abstention is an expected scientific outcome, not a claim of a successful real-world scientific finding.

The full container command retained networking disabled, non-root execution, a read-only root/data mount and writable temporary storage. TLS smoke used only temporary credentials/certificate and synthetic records on local loopback, with the child process stopped afterwards. The production tag is cumulative Phase 2 + Phase 3; the Phase 2 tag remains available. No public endpoint, cloud resource, paid LLM, dataset acquisition or load benchmark was started. API/cloud spend: **USD 0**. Local CPU, disk and package-download bandwidth were used; no new RSS/throughput measurement is claimed.

## Limits and next smallest task

This is service-client authorization for one offline API process, not a public SaaS platform, federated identity service or OS tenant sandbox. Provision/restrict the real credential directory and TLS keys before operator activation. Revocation requires restart; rate buckets are process-local and reset on restart. Idempotency metadata is retained with a 5,000-job ceiling. No automatic cross-process resume, distributed scheduling, retry queue, paid submission, raw artifact downloads or full-dataset execution is exposed. Certificate/proxy deployment and public access have not been provisioned.

Input-size/node/edge gates and trusted CLI execution are tested; broad fuzzing, production load, disk quotas, full dependency/OS image scanning, multi-host isolation, backup restoration and production SLOs belong to later gates. The exact original cause of the earlier package download stalls remains undetermined; normal builds are now verified.

Phase 3's scoped acceptance criteria are met. The next smallest Phase 4 task, after approval, is to audit the new envelope against the existing durable workflow store and specify safe restart/recovery/admission behavior before expanding concurrency. No Phase 4 implementation was started.
