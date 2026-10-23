# BLACKGRID 1.0.0 — restricted single-host release

This closes the nine-phase production-engineering scope for the existing local deployment. It preserves all 18 registered tools, scientific specifications, model routing, checkpoints and cost limits. It does not establish general scientific efficacy or unrestricted public-production readiness.

Read [readiness and remaining gates](report.md), [benchmark evidence](benchmark.md), [the operations handbook](operations.md), [release notes](release_notes.md) and [architecture](architecture.md).

## Daily use

From the existing `C:\Blackgrid` installation:

```powershell
docker compose up -d --no-build
docker compose exec blackgrid python -m blackgrid.operations health --readiness
.\.venv\Scripts\python.exe scripts\open_dashboard.py
.\.venv\Scripts\python.exe scripts\ask_api.py --question "Which nodes bridge communities?"
```

`ask_api.py` defaults to mock mode. Use `--live` only for an explicitly intended paid request under the existing grant. The dashboard uses the existing operator token; secrets remain local under `.secrets`. Do not place the token in a URL or commit it. Existing `.venv` activation is unnecessary when using the full Python path above.

## Checks and promotion

GitHub Actions [release checks](../../.github/workflows/ci.yml) build locked production/test images, run linting, scoped formatting and strict type checks, full offline regression, API/security tests, isolated staging/restore and an exact-image scan. CI uses synthetic fixtures, no production credentials/data, read-only repository permissions and pinned actions. Its two raw-CollegeMsg checks may skip because redistribution is not authorized; the local full suite executes them with the existing read-only input. Test failures, unexpected skips, missing scan coverage, stale evidence, critical findings or fixable high findings fail closed.

The [manual release workflow](../../.github/workflows/release.yml) reruns verification and presents an operator handoff through `release-review`. GitHub environment reviewers/branch restrictions must be configured by the repository owner; merely naming an environment does not configure protection. No cloud runner, remote production access or registry publication is provisioned.

The local production pipeline is:

```powershell
.\.venv\Scripts\python.exe scripts\package_release.py
.\.venv\Scripts\python.exe scripts\promote_phase9.py
```

Run it only after generating **fresh matching** regression, scan, staging and reconciled benchmark evidence under `docs/production_phase9`, with the prior service idle. Packaging records identities; it does not run checks or approve a release by itself. Promotion validates hashes, image identity, configuration, fresh scan/database, regression/recovery and final load outcomes, then creates a private offline backup, deploys, verifies exact mock results/restart/ledger retention, rolls back to the prior immutable image with the **current** state, and returns to the release. It does not restore old billing records. Preserve every attempt; archive/version the evidence directory before repeating this phase, rather than overwrite measurements.

Build commands for a fresh verification environment:

```powershell
uv sync --frozen --all-extras --group quality
docker build --target test -t blackgrid:phase9-test .
docker build --target production -t blackgrid:phase9 .
docker build --target benchmark -t blackgrid:phase9-benchmark .
```

The full container commands are encoded in the CI workflow, with bounded memory/CPU/PIDs and no worker network. The final load repeats the unchanged Phase 6 v2 protocol on the Phase 9 image with caching enabled:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase6.py --image blackgrid:phase9 --benchmark-image blackgrid:phase9-benchmark --reports docs\production_phase9\benchmark --tool-cache
```

The runner retains its attempt and private isolated credentials/state. Reconcile the resulting attempt with `scripts/report_phase6.py ATTEMPT_DIRECTORY`. It never submits benchmark work to production. The workload and stop limits are registered in [Phase 9](../../protocols/production_phase9_v1.json) and the referenced [Phase 6 v2 protocol](../../protocols/production_phase6_v2.json).

Implementation references: [GitHub workflow hardening](https://docs.github.com/en/actions/reference/security/secure-use), [environment configuration](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments), [Ruff configuration](https://docs.astral.sh/ruff/configuration/). Formatting covers the three new verification files, fatal lint rules cover application/tests/scripts/benchmarks, and strict typing covers `release_gate.py`; this is not a claim of repository-wide formatting or type completeness.
