# BLACKGRID — Production roadmap and Phase 2 proposal

Updated 22 October 2026. Phases 1–3 are complete for their documented scope. Phase 2 evidence includes successful image builds, 548 passing Linux container tests, exact offline host/container parity, clean restart, interrupted-task recovery and post-resume readiness; see its [completion report](docs/production_phase2/report.md). The user's subsequent approval authorized Phase 3: the bounded authenticated API is implemented with 574 passing Linux tests and a native HTTPS/restart check; see [Phase 3 scope and limits](docs/production_phase3/report.md). Analytical kernels and agent workflows were preserved. Phase 4 and later phases await explicit approval. The detailed original brief remains in [PRODUCTION_READINESS_PHASES.md](PRODUCTION_READINESS_PHASES.md).

Read [architecture](architecture.md), [prioritized gaps](production_gap_analysis.md), [dependencies](dependency_map.md), and [baseline evidence](baseline_test_report.md). Production phases are separate from the older research phases in PROJECT_CONTEXT.md.

## Phase sequence

| Phase | Smallest engineering scope | Evidence required to exit |
|---|---|---|
| 1 — Audit | Map current implementation, preserve dirty working tree, record safe tests, prioritize gaps, propose deployment | Five audit documents plus actual test evidence and stated limitations |
| 2 — Deployment foundations | One non-root container, explicit image/context allowlist, locked Python environment, read-only inputs, persistent local state, lifecycle/health checks | Offline workflows and parity pass in image; restart/termination and persistence checked; secrets/raw data absent from image |
| 3 — API and access control | Preserve local console; secure production interface around existing workflows, ownership/isolation, schemas, rate limits, idempotency, versioning | Unauthorized and cross-owner access rejected; duplicate/malformed requests safe; documented API contracts |
| 4 — Reliable execution | Reuse LangGraph and operations store; persistent job envelope, bounded admission, atomic budget reservation, cancellation, recovery and retry scheduling | Fault and concurrency tests show consistent authoritative state; no blind replay of uncertain billable calls |
| 5 — Observability | Redacted events, request/run/operation correlation, real service/job/tool/provider measurements, dashboards and runbooks | Trace a job end-to-end; diagnose representative failures; cost measurements reconcile; SLOs use measured baseline |
| 6 — Benchmarking | Bounded synthetic datasets/users; separate API, tools, agent, mock-LLM and approved real-LLM categories | Configured hardware/workload/seeds, raw measurements and reproducible reports; resource stop thresholds enforced |
| 7 — Resilience/security | Controlled failures, input attacks, access-control regressions, dependency/image scans and consistent restore drill | Evidence for recovery and isolation; critical findings fixed or release blocked; restore verified |
| 8 — Measured optimization | Profile Phase 6 workloads; optimize only proven bottlenecks; evaluate scaling when warranted | Same-workload before/after measurements plus scientific, agent and security regression safety |
| 9 — Release | CI/CD, staging/production gates, migrations/rollback, operations handbook and final evidence-based readiness report | Reproducible approved deployment, security/recovery/SLO evidence, compatible existing workflows and honest limitations |

No phase is complete solely because code exists. Each phase requires review of actual files, resource estimates, compatibility risk, acceptance evidence and user approval to continue. Cloud resources, publication, large workloads and paid calls have their own authorization requirements. Kubernetes remains conditional on measured need.

## Concrete Phase 2 proposal

**Goal:** package the existing application for a single-host, offline-by-default deployment while preserving the source layout, numerical behavior, LLM sequence, checkpoints and reports. Do not introduce a new service architecture.

### Proposed file changes

| File | Proposed change | Risk / complexity |
|---|---|---|
| `.dockerignore` (new) | Allowlist build inputs; exclude Git history, `.env*` except example, raw data, `.venv`, backups, caches, logs, private run artifacts, sealed tests and unreviewed output | Medium: omissions can leak data or remove required assets |
| `Dockerfile` (new) | Python 3.11 base pinned at implementation time; frozen lock install; non-root user; explicit source/config/protocol/template copy; no paid startup; exec-form command | Medium: native numerical packages, optional methods and Linux parity need verification |
| `docker-compose.yml` (new) | One application service; resource limits, read-only inputs/root where feasible, writable state/temp mounts, shutdown grace period; no DB/Redis/object-store service by default | Medium: filesystem permissions, evidence mounts and persistent state identity |
| `docs/deployment.md` (new) | Build/start/offline commands, directory mapping, required forecast/research assets, secret setup, health, graceful shutdown, backup and rollback | Low–medium |
| `src/blackgrid/operations/health.py` or an equivalently small deployment module (proposed new) | Local liveness/readiness command: inspect runtime/config/mount permissions and required selected-mode evidence without LLM calls or analyses | Medium: health must report missing capability honestly without mutating scientific state |
| `src/blackgrid/cli.py`, `console/server.py` (only if needed) | Minimal lifecycle hooks for termination, admission stop and worker drain; preserve loopback/auth guards and defaults | Medium–high: in-flight daemon work, cancellation and native calls need explicit policy |
| `pyproject.toml` / `uv.lock` (only if needed) | Declare an already-used direct dependency or necessary packaging assets; no incidental upgrades | Medium: preserve locked environment and numerical parity |
| `tests/test_deployment.py` or focused deployment tests (new) | Validate configuration, health, missing evidence, permissions and zero-provider-call startup; container smoke/restart checks | Medium: cross-platform execution and runtime availability |
| `.env.example` (only if needed) | Document validated deployment configuration with placeholder values | Low; no secrets |

These are proposed paths, not created implementation files. Confirm exact runtime availability at phase start; Docker availability/build/network/image access has not been tested in Phase 1. Do not install or provision it automatically. Resolve immutable image/tool versions when implementation is authorized rather than inventing a digest now.

### Deployment and compatibility decisions

1. Preserve `/app/src/blackgrid` source layout initially so `REPO_ROOT` remains meaningful. Mount reviewed state/evidence at paths matching current consumers, with data read-only and runtime output writable. Explicitly inventory which research/forecast files are required; do not mount the entire private repository or copy all historical runs into an image.
2. Ship one application service first. Keep SQLite databases and artifacts on the same host with documented consistent backups. Host PID leases cannot safely coordinate independently isolated worker containers; do not scale replicas or share this store across containers/hosts until Phase 4 addresses ownership.
3. Keep mock mode and no paid startup as defaults. Live secrets are injected only for explicitly authorized workloads; pricing/budget failures must remain hard stops. Container egress controls must distinguish offline workers from approved provider access.
4. Keep the console loopback-only. Publishing a Docker port does not expose a process bound to container loopback. Phase 2 should validate CLI workloads/internal console health without weakening the bind or claiming a remotely usable UI. Authenticated remote ingress is Phase 3; any earlier host-access adapter requires explicit design review.
5. Include optional method support only through an explicit profile with compatibility and license checks, or document it as unavailable rather than silently substituting a different algorithm. Preserve all supported installed-host behavior in the regression comparison.
6. Define graceful stop as stop admission, request cooperative cancellation/drain, wait a documented grace interval, then record interrupted/resumable state. Do not claim immediate cancellation of native numerical work or exactly-once external model billing.
7. Use existing tiny fixtures and saved evidence for smoke checks. If native platform differences occur, report predefined numerical tolerances; do not change protocols, seeds or expected scientific conclusions to obtain a pass.

### Acceptance and rollback

- Build image with the existing lock and verify required console/template/protocol assets. Inspect image content/history for excluded sensitive material.
- Start without credentials and verify no live transport or paid call occurs. Validate missing config/data/evidence yields an explicit unavailable/failed readiness outcome.
- Run appropriate offline regression and small end-to-end parity checks in the container; compare artifacts and current source hashes, recording platform/tolerance differences.
- Verify non-root execution, writable state, read-only inputs, enforced resource settings, liveness/readiness and cleanup.
- Stop/restart during a controlled mock workflow; verify checkpoint/ledger/artifact integrity and documented resume behavior. Repeat from a clean deployment environment before calling deployment reproducible.
- Roll back by retaining the prior source/image and consistent state backup. Do not restore old spending ledgers over newer billable operations; reconcile them first. Any schema migration requires a tested compatibility and restore plan before applying it.

Estimated complexity is **medium overall, with higher-risk lifecycle and native-package validation**. This is not a measured time estimate or promise. No cloud budget or paid LLM execution is needed for the proposed offline validation; image/dependency download availability and local storage/CPU costs must be established at phase start.

## Readiness checklist

- [x] Phase 1 source/interface/persistence/dependency map documented.
- [x] Existing working-tree changes recorded and preserved.
- [x] Production gaps prioritized with evidence and limitations.
- [x] Baseline tests executed; outcomes and environmental restrictions recorded in the baseline report.
- [x] Phase 2 changes, risks, checks and rollback proposed.
- [ ] Phase 2 implementation approved and verified.
- [ ] Authenticated production API and ownership isolation verified.
- [ ] Durable job admission, concurrent budgets and bounded worker recovery verified.
- [ ] Operational metrics/traces/alerts and measured SLOs verified.
- [ ] Reproducible workload capacity and resource limits measured.
- [ ] Security scans, fault scenarios and consistent restoration verified.
- [ ] Measured optimizations and deployment/release gates passed.

The next smallest task is the approved Phase 2 deployment foundation. Do not begin it without the user's continuation approval.
