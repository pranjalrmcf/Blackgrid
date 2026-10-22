# BLACKGRID — Phase 1 baseline test report

Executed 22 October 2026 against the existing dirty working tree, base commit `e043496720445ac2f0ac79db51532f52159b0071`. Application code, tests, configs and dependency lock were not changed. This is engineering regression evidence, not a fresh scientific efficacy or performance benchmark.

## Actual outcomes

| Execution | Passed | Failed | Errors | Skipped | Reported elapsed |
|---|---:|---:|---:|---:|---:|
| Complete existing suite, restricted sandbox | 520 | 10 | 0 | 0 | 294.38 s |
| Focused console diagnosis, restricted sandbox, stopped at first failure | 2 | 1 | 0 | 0 | 0.59 s |
| Complete console module, approved outside-sandbox rerun | 13 | 0 | 0 | 0 | 19.21 s |

All ten complete-suite failures were console HTTP tests blocked by `PermissionError: [WinError 10013]` on loopback connections. The focused diagnosis confirmed that same restriction. After user-approved escalation, all 13 console tests passed without a code or test change. All ten failing node IDs are covered by passing tests in that rerun; three console tests also passed in the original run. Thus the combined evidence covers all 530 distinct collected cases with passing outcomes. **This is not a claim that one unrestricted full-suite invocation passed**; the initial failed run is retained, and no tests were skipped, deleted, relaxed or marked expected-failure.

No unresolved application test failure was observed in these executions. This does not establish absence of defects, security vulnerabilities, production capacity, or all-platform correctness.

## Commands and artifacts

Complete baseline command (stdout/stderr saved to the log):

```powershell
.venv/Scripts/python.exe -m pytest -o addopts= -q --tb=short --durations=15 --junitxml=docs/production_phase1/baseline_tests.xml --basetemp=tmp/production-phase1-pytest
```

Diagnostic command:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_console.py -o addopts= -q -x --tb=short --basetemp=tmp/production-phase1-console-diagnostic
```

Approved outside-sandbox rerun:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_console.py -o addopts= -q --tb=short --junitxml=docs/production_phase1/console_unrestricted.xml --basetemp=tmp/production-phase1-console-unrestricted
```

- [Complete baseline log](docs/production_phase1/baseline_tests.log) and [JUnit XML](docs/production_phase1/baseline_tests.xml).
- [Focused diagnostic log](docs/production_phase1/console_diagnostic.log).
- [Outside-sandbox console log](docs/production_phase1/console_unrestricted.log) and [JUnit XML](docs/production_phase1/console_unrestricted.xml).
- [Machine-readable outcome and integrity summary](docs/production_phase1/baseline_summary.json).
- [Source hashes, initial Git status, dependency versions and source inventory](docs/production_phase1/source_snapshot.json).

The baseline started at 13:06:27 IST; the console rerun started at 13:08:04 IST and overlapped part of the full run. Their durations must not be added as exclusive wall time or compared as performance improvements. The full-suite XML reports 294.347 seconds and pytest rounds its final summary separately. Times here are observed on this host/environment only, with no controlled CPU/cache/load experiment.

## What was exercised

The 38 test modules cover contracts, dataset parsing/checksums/window selection, duplicate/missing-edge semantics, synthetic generators, community/null calculations and sensitivity, tool allowlists and refusal paths, numerical/report evidence checks, routing and completion obligations, forecasting/temporal isolation/model selection, behavioral methods, synthetic research diagnostics, durable operations/checkpoints/locks, interruption/reconciliation, budget termination/overruns, CLI/replay, and console safety/rendering. Detailed node-level outcomes and timings are in the XML files.

Existing offline fake providers exercise live-mode authorization/billing/error code paths without real model execution. Transport tests validate endpoint rejection and a very short child-process deadline; they do not establish provider reliability or real-LLM quality. Console tests start short-lived loopback HTTP servers. Dataset tests include existing local CollegeMsg checksum/window and full-scope checks; raw records were not included in audit reports or external prompts. The D-003 local-use resolution and later scope decisions were reviewed as existing records, not expanded into redistribution rights.

Tests run existing small numerical/evaluation fixtures; no new load benchmark, large graph run, held-out efficacy study, or paid experiment was initiated. Mock/scripted outcomes do not demonstrate improvement in real research reliability.

## Environment, integrity and resources

Python 3.11.9 on Windows, using the existing `.venv` and existing installed packages. Exact platform/package metadata and lock hash are in the source snapshot; key packages include pytest 9.1.1, LangGraph 1.2.12, NetworkX 3.6.1, NumPy 2.4.6, Pydantic 2.13.5, scikit-learn 1.9.1 and SciPy 1.17.1. Optional igraph/Leiden packages were already installed. No package installation, lock update, infrastructure provisioning or paid LLM workload occurred. API/cloud spend initiated by this phase: **USD 0**.

Post-test SHA-256 checks matched all 111 snapshotted Python source/test files, config files, `pyproject.toml` and `uv.lock`. The initial working tree already contained modified application files, README/report changes and untracked Sprint 8 work. These were preserved; HEAD alone does not identify this baseline.

The run wrote audit logs/XML and existing-test temporary/cache artifacts. CPU utilization and peak memory were not measured; no throughput or capacity claim is made. Windows CIM queries for CPU/RAM metadata were unavailable under the sandbox, so hardware model/capacity are not newly verified here. No attempt was made to install system tools or change permissions to obtain them.

## Phase 1 acceptance

| Criterion | Result and evidence |
|---|---|
| Existing architecture documented | [architecture.md](architecture.md), with actual routes, workflow, persistence and scientific boundaries |
| Production gaps prioritized | [production_gap_analysis.md](production_gap_analysis.md), distinguishing observed controls, missing controls and untested static risks |
| Existing functionality/dependencies mapped | [dependency_map.md](dependency_map.md) plus recursive source inventory and focused code review |
| Baseline tests recorded | Executions above; environmental failures retained and covered by successful targeted rerun |
| No major architecture/code modification | Application/test/config/lock hashes unchanged; documentation and execution evidence only |
| Phase 2 proposal reviewable | [production_roadmap.md](production_roadmap.md), with proposed files, complexity, compatibility risks, acceptance and rollback |

Phase 1 is complete within this audit scope. Production deployment, remote security, multi-worker budget correctness, restore behavior, native Linux/container parity and measured scalability remain unvalidated. Phase 2 is the next smallest task and awaits explicit user approval.
