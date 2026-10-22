# Docker dependency-download investigation

22 October 2026. Scope: ordinary Docker/uv build reliability only. Application, numerical, agent, API, experiment and evaluation code are unchanged by this investigation.

## Findings

The observed failure is a wheel-response download timeout, not demonstrated SciPy compilation or a dependency conflict. Earlier build output failed extracting/downloading the precompiled **igraph** wheel after network timeouts; NumPy and other packages retried too. A separate Python HTTP request inside Docker returned HTTP 200 and the first 1,024 bytes of the locked NumPy wheel, while a complete-wheel read timed out. This supports an unreliable large-response transfer path; it does not identify a specific DNS, proxy, VPN, TLS implementation or upstream fault.

Docker currently reports Linux x86-64, 22 CPUs and 16,591,138,816 bytes of engine memory. Its configured outbound proxy is `http.docker.internal:3128`. Proxy configuration alone does not prove that the proxy caused the failure. BuildKit history showed one current BLACKGRID build and completed/failed earlier attempts, not overlapping active BLACKGRID builds.

The unchanged lock contains compatible precompiled wheels:

| Dependency | Locked version | Linux wheel compatibility |
|---|---|---|
| NumPy | 2.4.6 | CPython 3.11, manylinux 2.27/2.28 x86-64 |
| SciPy | 1.17.1 | CPython 3.11, manylinux 2.27/2.28 x86-64 |
| scikit-learn | 1.9.1 | CPython 3.11, manylinux 2.27/2.28 x86-64 |
| igraph | 0.11.9 | CPython 3.9 stable ABI, manylinux 2.17 x86-64 |
| leidenalg | 0.10.2 | CPython 3.8 stable ABI, manylinux 2.17 x86-64 |

The installed matching-version metadata requires NumPy `>=1.26.4,<2.7` for SciPy, and NumPy `>=1.24.1` plus SciPy `>=1.10.0` for scikit-learn. The locked versions satisfy these constraints. No compiler activity or out-of-memory failure was observed in the reviewed logs. Disk exhaustion has not been separately measured; existing error output identifies network reads rather than a no-space error.

## Initial investigation and execution

No implementation/build file has been modified during this investigation. `uv.lock` and `pyproject.toml` are preserved. `before.json` records hashes and package requirements. No alternative package manager, wheelhouse workflow, dependency downgrade, disabled security feature or Docker infrastructure rewrite has been introduced.

At the user's request, verification uses the normal build with its existing configurable timeout and concurrency, retaining BuildKit cache mounts and optional Leiden dependencies:

```powershell
docker build --target production -t blackgrid:phase2 --progress=plain --build-arg DOWNLOAD_TIMEOUT=600 --build-arg DOWNLOAD_CONCURRENCY=1 .
```

The attempt's plain output is in `production_build.log`. Cached earlier layers/packages were reused; SciPy was the remaining reported download. The attempt began at 10:29:14 UTC and was manually interrupted after more than eight minutes without further visible progress. This is a bounded, interrupted attempt, not a completed build or a demonstrated SciPy installation failure. **Build completion, imports, production/test images, container tests, entrypoint, runtime user, health and installed-lock parity remain unverified.** Historical Windows regression results are not substituted for these checks. No further retries were started.

The next smallest step is to retry the same ordinary build on another available network, or check Docker Desktop's outbound proxy settings with the user. Neither option requires application or dependency-version changes. Local development and Windows tests can continue while container verification remains incomplete.

## Normal commands after a successful build

```powershell
cd C:\Blackgrid
docker build --target production -t blackgrid:phase2 --progress=plain --build-arg DOWNLOAD_TIMEOUT=600 --build-arg DOWNLOAD_CONCURRENCY=1 .
docker build --target test -t blackgrid:phase2-test --progress=plain --build-arg DOWNLOAD_TIMEOUT=600 --build-arg DOWNLOAD_CONCURRENCY=1 .
docker run --rm --network none --read-only --tmpfs /tmp:size=512m,mode=1777 --mount "type=bind,source=C:\Blackgrid\data,target=/app/data,readonly" blackgrid:phase2-test
docker compose config --quiet
docker compose up -d --no-build
docker compose exec blackgrid python -m blackgrid.operations health --readiness
```

These commands are instructions, not verification results. No paid calls, unrelated experiments, dataset acquisition or public image publication were initiated.

## Subsequent successful builds and container test repair

The user subsequently supplied successful ordinary production and test build output. SciPy downloaded in approximately seven seconds in that production build. This demonstrates that the locked dependencies can install normally; the exact cause of the earlier transient transfer failures remains undetermined.

On the user's request to inspect a large test error directly, the original full container command reproduced **531 passed, 4 failed, 11 errors** in 189.95 seconds (`container_tests.log`). Causes were a missing public development registry, a missing Sprint 4 review rubric, and Sprint 7 evaluation invoking Git unconditionally in a runtime image without Git. These were not dependency installation failures.

The build allowlist now admits only those two additional files. The public development registry is copied into the test target; the rubric is copied into runtime because evaluation code hashes it. No raw data, saved runs, credentials or sealed benchmarks are added. Sprint 7 provenance collection now bounds Git calls to ten seconds, checks return codes, and records revision/dirty status as null when Git or checkout metadata is unavailable; source and lock hashes remain present. Two regression cases cover missing Git and unavailable checkout metadata.

Both corrected images built successfully with ordinary Docker commands (`test_rebuild.log`, `production_rebuild.log`). Production is tagged `blackgrid:phase2` and `blackgrid:latest` to match both Compose and the user's initial command. The complete corrected container suite passed: **548 passed in 219.87 seconds**, exit code 0 (`container_tests_fixed.log`). This includes the two new provenance regression cases. Tests ran with networking disabled, a read-only root and data mount, writable temporary storage, and the image's non-root user. No paid calls or dependency version changes were needed. Runtime startup/health/restart acceptance remains a separate pending check.
