# Phase 2 — Deployment foundations verification

Date: 22 October 2026. Status: **Phase 2 complete for the documented single-host, offline deployment scope**. Phase 3 remains unapproved. See [deployment instructions](../deployment.md), [roadmap](../../production_roadmap.md) and the machine-readable evidence in this folder.

## Changes and preservation

- Added a source-layout, non-root production image with pinned Python/uv base digests and frozen dependencies, including the existing optional graph methods. A separate verification target contains pytest/tests.
- Added an allowlisted Docker build context, one-service Compose configuration, read-only data/root, persistent local state, disabled runtime networking, one CPU/2 GiB/process limits and no published port.
- Added validated deployment settings, offline startup/readiness checks, a guarded local liveness endpoint and bounded console shutdown/draining. Existing local CLI/provider authorization behavior is preserved.
- Added deployment regression tests and `scripts/verify_deployment.py` for real container boundary, offline parity, restart, interrupted-workflow recovery and post-resume readiness checks.
- Added operator documentation and commented non-secret configuration examples. No database schema migration or dependency-lock change was made.

The pre-Phase-2 snapshot records existing user changes. The initial implementation changed only `src/blackgrid/cli.py` and `src/blackgrid/console/server.py` among existing snapshotted code files. Subsequent container verification also changed `src/blackgrid/evaluation/sprint7.py` to handle unavailable Git provenance explicitly, and `tests/test_sprint7.py` added two regression cases. Numerical kernels, planner/critic/provider code, prompts/models and workflow graph were preserved by this phase. New operations modules wrap the application. The earlier `verification_summary.json` describes the initial Windows verification snapshot, not this final inventory.

## Executed Windows checks

| Execution | Result | Scope |
|---|---|---|
| Initial deployment/CLI checks | 23 passed in 14.21 s | Startup validation, offline readiness, lifecycle and existing CLI |
| Full regression | 543 passed in 273.38 s, zero failures/errors/skips | Full existing suite plus initial deployment tests |
| Final health/console/CLI checks | 39 passed in 18.85 s | Includes three later health cases and the final health parsing adjustment |

The full regression preceded the last three health cases; the focused run verifies those additions. Combined passing evidence covers 546 distinct cases; this is not a claim that all 546 ran in one Windows invocation. [Verification summary](verification_summary.json), [full JUnit](regression.xml), [full log](regression.log), and [final focused JUnit](final_focused.xml) retain actual outcomes.

A fresh current-source Windows first-window CollegeMsg investigation also completed in mock mode with status `completed`, verdict `not_supported`, one mock planner call and USD 0. It uses the existing local-use decision and frozen science; raw records stay local. [Host execution log](host_offline_run.log); local artifacts are under `tmp/phase2-host-reference/`. This is a parity reference, not a new confirmatory research study.

## Container verification status

Docker Desktop initially failed to start because it could not remove stale local socket endpoints. A guarded, approved repair preserved its two-endpoint runtime folder at `C:\Users\pranj\AppData\Local\Docker\run.phase2-backup-20261022-134519`. Docker later reported another socket error in its Secrets Engine. At the user's request, Docker Desktop/backend were closed and troubleshooting was handed back. The user subsequently restored startup; the engine was verified as Docker 29.5.2, Docker Desktop 4.75.0, Linux amd64. No factory reset, settings reset, dataset move or Docker data deletion was performed by this work.

The first production build failed downloading locked wheels with uv's 30-second timeout. It is retained in [docker_build.log](docker_build.log). The bounded retry uses a 180-second timeout, two retries, two concurrent downloads and a BuildKit public-package cache; package versions and hashes remain unchanged. [Retry log](docker_build_retry.log). A containerized 1 KiB request to the actual locked NumPy wheel returned HTTP 200; [probe evidence](network_probe.log).

The user subsequently completed ordinary production and test builds. Direct container regression reproduced 531 passes, four failures and eleven setup errors from omitted development registry/review rubric files and unguarded Git invocation. The narrowly corrected images built successfully; the full offline container suite then passed **548 tests in 219.87 seconds**, including two new provenance cases. See [build investigation and repair report](../docker_build_investigation/report.md) and [passing Linux test log](../docker_build_investigation/container_tests_fixed.log).

The user executed the acceptance harness successfully; [saved acceptance evidence](container_acceptance/container_acceptance.json) reports `status: passed`, with [command log](container_acceptance/container_commands.log). A separate new state volume/container verified:

- Production imports, UID 10001, pytest absent, and checked private inputs/credentials absent.
- Disabled networking, read-only root/data, one CPU, 2 GiB memory and 128-process configuration.
- A complete offline run with exact scientific fingerprint equality to the Windows reference.
- Clean termination/restart with completed state preserved.
- An in-flight task interrupted with bounded exit code 2, without an OOM kill.
- Resume after verified process termination, exact reference parity, and successful post-resume readiness.

The user's Compose service also returned `ready` with no failures. This is a fresh-state container reproduction using built images and cached dependency layers, not a claim of an uncached rebuild on an independent host. Checks are limited to the stated offline workload; forecast/research deployment assets, live providers, capacity and broader security remain outside this acceptance.

## Limits, resources and next gate

No paid LLM, cloud provisioning, public image publication or load benchmark was initiated. API/cloud spend for these checks is USD 0; local build bandwidth/storage and CPU were used. Full CPU/RSS telemetry and vulnerability scanning are not claimed. Production capacity, tenant security and multi-host coordination remain outside Phase 2.

The default image/service is offline and declares community readiness. Forecast/research need explicitly provisioned reviewed evidence at the preserved source-layout paths; absence must not be described as full capability parity. The console remains inside container loopback, so a host browser cannot access it. A new empty volume is not permission to reset historical paid budgets. SQLite PID leases remain single-host/process-namespace mechanisms; interrupted restart recovery may require an operator-verified force unlock.

Phase 2 acceptance is recorded. The next smallest task, after Phase 3 approval, is to audit existing console routes and define the minimal authenticated API and ownership contract before implementation. Phase 3 covers authenticated access, validated requests, idempotency and rate limiting while preserving scientific/agent logic.
