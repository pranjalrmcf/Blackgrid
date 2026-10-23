# Single-host deployment foundations

Updated 23 October 2026. The existing single Compose service runs the cumulative Phase 7 authenticated API over localhost HTTPS, preserving all 18 tools, earlier reliability/security/monitoring work and the original state volume. See [API contracts](api.md), [live dashboard guide](production_phase6/guide.md), [Phase 7 verification and residual security findings](production_phase7/report.md), and [private backup/restore and incident response](production_phase7/runbook.md). Mock is the default; explicitly authorized live requests use the retained budget. The endpoint remains local. Compose uses `blackgrid:phase7` with a pinned Debian Trixie base and unchanged Python 3.11.17; earlier phase-specific image commands below are historical verification instructions.

## Layout and boundaries

The production image keeps source at `/app/src`, configs at `/app/configs`, protocols at `/app/protocols` and the current `REPO_ROOT` layout. The dependency environment comes from `uv.lock`, with existing optional methods included. A separate `test` target includes pytest and tests; the final production image contains neither. Python/uv base images are pinned by registry-inspected digests. The Linux base uses Python 3.11.17; the existing Windows baseline uses 3.11.9. Numerical/native/platform parity needs executed verification, not assumption.

The explicit build context excludes credentials, raw data, private runs/results, old backups, caches, Git history and sealed files. Runtime data is mounted read-only, state is a named volume, `/tmp` is bounded ephemeral storage and the root filesystem is read-only. UID/GID are 10001, capabilities are dropped, new privileges are disabled, and the Compose process limit, 2 GiB memory ceiling and one-CPU allowance bound this first deployment. These controls require a working Linux Docker engine and runtime inspection to call them verified.

Compose starts `api` from cumulative image `blackgrid:phase7`, publishing only `127.0.0.1:8765`. TLS and bearer authentication are required for job routes. A normal bridge is necessary because this Docker engine does not publish ports for containers attached only to an internal network. The API server has bridge connectivity; its Linux job subprocesses install a non-removable kernel seccomp filter denying socket creation, connect and io_uring before importing the trusted CLI. Worker containment fails closed on unsupported Linux architectures or filter-install failure. Supported architectures are Linux x86-64 and aarch64; host development on other systems remains trusted-tools-only. This filter is a network boundary, not a general arbitrary-code sandbox. Existing filesystem/resource controls remain in force.

The old local console remains available through its CLI command but is not served by this API listener. Existing data and `blackgrid_blackgrid-state` are retained. Older shared CLI runs are not automatically exposed as client-owned API jobs.

## Prerequisites and build

- Working Docker Engine/Desktop in Linux-container mode and Docker Compose.
- Existing local CollegeMsg input at `data/CollegeMsg.txt/CollegeMsg.txt`, with the checksum and local-use decision recorded in the selected configuration. No raw data is downloaded or bundled.
- Explicit read-only provisioning of saved forecast/research evidence if those capabilities are required; see below.
- Internet access for the initial approved build to fetch pinned public images and locked dependencies. Runtime defaults require no internet, provider credentials or paid services.

From the repository root:

```powershell
# One-time local provisioning in a private, Git-ignored directory:
.\.venv\Scripts\python.exe scripts/create_api_client.py --subject alice
.\.venv\Scripts\python.exe scripts/setup_local_tls.py
.\.venv\Scripts\python.exe scripts/configure_api_live.py --subject alice
# Reuse existing files on subsequent starts; do not overwrite/rotate credentials blindly.
docker compose config --quiet
docker compose build --progress=plain
docker compose up -d
docker compose ps
docker compose exec blackgrid python -m blackgrid.operations health --liveness
docker compose exec blackgrid python -m blackgrid.operations health --readiness
curl.exe --cacert .secrets/server-cert.pem https://localhost:8765/health/ready
```

The TLS helper uses OpenSSL (including Git for Windows' bundled executable), creates a 90-day certificate with localhost/127.0.0.1 SANs, and preserves existing files. Restrict `.secrets/` to the operator/service account before provisioning; Windows ACLs are required because POSIX file modes alone do not restrict Windows access. The active local directory was restricted to its operator and SYSTEM. The registry, server certificate and key are mounted read-only; plaintext client tokens stay on the host. Private files never enter the build context. For command-line HTTPS clients, trust this certificate explicitly with `--cacert`; do not disable TLS verification or install a global trust exception. Renew before expiry through a deliberate operator rotation/restart.

Startup validates settings and the config, checks accepted local-use status and the input checksum without parsing events, verifies the template, and tests writable state/cache. It does not instantiate a provider, run an analysis, initialize a paid allowance, migrate historical state or create new research evidence. Missing config, input, evidence or writable state produces a sanitized failure code and nonzero exit. Restart is manual (`restart: "no"`) to avoid repeated failed startup or analysis loops.

To inspect ordinary CLI help/status in the already-running container:

```powershell
docker compose exec blackgrid python -m blackgrid --help
docker compose exec blackgrid python -m blackgrid status --runs-dir /app/runs
```

To run the existing first-window investigation offline, explicitly invoke it:

```powershell
docker compose exec blackgrid python -m blackgrid run /app/configs/collegemsg_sprint01.json --mode mock --data-root /app --runs-dir /app/runs --cache-dir /app/runs/cache
```

This computes real-data numerical tools using the recorded window and a scripted mock provider. It is not a real-model efficacy study. It retains the existing null/sensitivity protocol and resource/refusal behavior. Do not run a CLI investigation concurrently with a console action; this first deployment is serialized operationally, and concurrent cross-run paid admission is not yet verified.

## Environment and secrets

`blackgrid.operations` reads only these explicit process variables; it does not load the repository `.env`:

| Variable | Default | Validation / purpose |
|---|---|---|
| `BLACKGRID_ENV` | `production` | `development`, `test` or `production`; explicit deployment label |
| `BLACKGRID_CONFIG` | Source-root `configs/collegemsg_sprint01.json` | Validated existing mock config; absolute paths recommended |
| `BLACKGRID_DATA_ROOT` | Source root | Dataset path must resolve inside it; bytes must match config hash |
| `BLACKGRID_RUNS_DIR` | Source-root `runs` | Persistent writable directory; cache is its `cache` child |
| `BLACKGRID_PORT` | `8765` | Integer 1–65535; Compose publishes this only on host loopback |
| `BLACKGRID_SHUTDOWN_GRACE_SECONDS` | `30` | Finite positive number, at most 300 |
| `BLACKGRID_CAPABILITIES` | `community` | Comma-separated `community`, `forecast`, `research`; unknown/empty values rejected |

Examples for host-only development/testing use `BLACKGRID_ENV=development` or `test` with a separate runs directory and small fixture config. Environment labels do not bypass scientific or spending gates. Compose supplies fixed production defaults; a reviewed local override or `docker compose run -e` can change non-secret test settings. Keep stop grace greater than application drain grace.

Startup remains based on a validated mock configuration and performs no provider calls. Live requests separately require the operator's retained policy, private mounted provider key, authorized subject and explicit request flag. [Live API setup](api_live.md) reuses the existing host grant and imports historical spend/reservations without renewing it. Compose mounts only the key/policy files read-only; the complete host `.env` is not injected. Never treat a new state volume as a fresh spending grant. Do not put secrets in command arguments, build arguments, committed Compose environment files, logs or artifacts. A deployment without an existing live grant must omit the live-policy environment entry and its two mounts to remain mock-only; do not invent a grant.

## Saved evidence and capability readiness

The default declares community capability. The console can still display existing families; declaration is a readiness requirement, not permission to replace methods or fabricate unavailable evidence.

Forecasting consumes:

- `/app/runs/sprint6-v1/selection.json` and its frozen evaluation outputs.
- `/app/results/sprint06-v2/summary.json`.
- `/app/results/sprint06-v3-bitcoin/summary.json`.

Research review consumes the existing `/app/runs/sprint7-final/` bundle, including `sprint7_manifest.json` and every artifact it references. Copy or mount only reviewed, necessary assets, read-only, into these exact paths. Nested read-only bind mounts can overlay the relevant evidence folders inside the state volume. Use long-form Compose bind mounts with `create_host_path: false` to fail on missing host sources. Review data rights/privacy before moving any derived evidence; nothing from private `runs/` or `results/` is included in the image by default.

Set `BLACKGRID_CAPABILITIES=community,forecast,research` only after those assets are provisioned. Readiness checks presence and JSON-object shape; existing scientific consumers retain their own integrity/identity checks at use time. Health is not scientific evidence verification. Do not omit promotion evidence and then claim forecasting is equivalent: omission can change the existing selected method. No startup command regenerates evidence, trains a new model or silently substitutes a method.

## Health and lifecycle

`GET /health/live` and `/health/ready` are available through the local HTTPS endpoint and obey the explicit Host allowlist. They expose no credentials/raw records. The local health command uses HTTPS with certificate and hostname verification when `BLACKGRID_API_TLS_CERTFILE` is configured; otherwise it retains the original HTTP console probe. Readiness checks validated config/data, template, state writability, existing state and declared saved evidence. The Docker health probe has a ten-second overall deadline; readiness does not certify that a long analysis will finish within its budget.

The API uses Uvicorn shutdown plus its existing job drain/child termination policy. The retained console command uses its Phase 2 admission-stop/thread-drain behavior. The workflow graph, call order, prompts/models, budget ledger and numerical kernels remain unchanged. Incomplete API jobs retain interruption state without automatic replay; see [API recovery boundaries](api.md). A hard kill/OOM is a crash, not graceful cancellation.

```powershell
docker compose stop
docker compose start
```

After an interrupted workflow, inspect its status and receipts first. The existing PID lease is local to a process namespace. Container restart can reuse a PID and conservatively make an old lock appear alive. Only after verifying that the prior single application/worker process is stopped, use the existing explicit `resume ... --force-unlock` recovery option if needed. Never force-unlock a genuinely active worker. Do not run multiple replicas, share this state across hosts/containers, or assume cross-container PID ownership is safe. Phase 4 must address this before worker scaling.

## Offline verification

Build the explicit verification target; pytest/tests are excluded from the production target:

```powershell
docker build --target test -t blackgrid:phase4-tools-test .
docker run --rm --network none --read-only --tmpfs /tmp:size=512m,mode=1777 --mount "type=bind,source=C:\Blackgrid\data,target=/app/data,readonly" blackgrid:phase4-tools-test
```

To exercise the running Compose service over certificate-verified HTTPS (one offline job and a restart):

```powershell
.\.venv\Scripts\python.exe scripts/verify_compose_api.py
```

This reads the local client token in memory, verifies runtime mounts/limits and worker network denial, tests authentication/idempotency/results, and confirms persistence across restart. It never prints the credential. Do not run it while unrelated work is active; restart is part of the check.

Use an absolute data path appropriate to the host. Keep the test run serialized; its existing suites use small numerical fixtures and local-only HTTP tests. Linux fixture portability, optional methods and the baseline/working-tree version must be verified before claiming full parity. Test artifacts should be mounted to a separate authorized evidence directory when preserving logs; do not write into the read-only input mount.

Required verification includes: image build and content inspection; non-root UID; no secrets/raw records in image/history; expected mounts/limits/egress; startup without credentials; precise missing-input/evidence failures; offline scientific/regression parity; controlled mock interruption and restart; state and artifact consistency; and clean-environment reproduction. Record failures instead of relaxing science or test expectations. The [phase report](production_phase2/report.md) distinguishes checks actually executed from those blocked by the host runtime.

## Backup and rollback

The named volume retains the SQLite ledger, checkpoints, receipts, outputs and caches across container replacement. `docker compose down` preserves it; **do not use `down --volumes`** when state is needed. The earlier folder backup is a pre-Phase-1 snapshot, not a validated live-volume backup.

For a consistent state backup, stop and verify all writers are stopped, then copy the entire state volume with both SQLite files and their journal/WAL sidecars, receipts and artifacts together. Record hashes and source/image identity. Back up reviewed read-only evidence/config separately. A live directory copy is not guaranteed consistent. Restoration must be rehearsed before production readiness is claimed.

Rollback uses the prior source/image and a consistent, compatible state backup. This phase adds no database migration and does not reset spending. Never overwrite newer billable operations or unknown reservations with an older ledger; reconcile first. Keep prior images/backups until restore and backward-compatibility checks pass. Deployment does not expand rights to redistribute datasets or publish private artifacts.
