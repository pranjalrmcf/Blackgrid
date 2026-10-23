# Phase 7: resilience, security and restore verification

Completed 23 October 2026 for the documented local, single-host, trusted-tool scope. The cumulative `blackgrid:phase7` image is deployed on the original state volume. It retains Phases 1–6 and all 18 registered tools. vLLM and Phase 8 remain outside this work. This is not an external security certification or approval for public deployment.

## Changes and defects found

Added a private offline API-state backup/restore module. It obtains service and execution leases, rejects active writers/links/unsafe destinations, uses SQLite backups, normalizes WAL databases into self-contained files, hashes every file and publishes only new validated destinations. Restore never overwrites existing state or spending records. File/byte/time limits and stable, non-sensitive CLI failures are enforced. See [the recovery and incident runbook](runbook.md).

A genuine partial-artifact test exposed an API defect: malformed result JSON returned a generic 500. Result validation now returns the existing stable `409 results_unavailable` response and preserves the job record. The test verifies cross-owner denial and successful retrieval after restoring the intact artifact. No scientific calculation, prompt, model, tool-selection rule or paid limit changed.

The first real snapshot drill exposed a WAL issue missed by simple fixtures: SQLite verification could create sidecars beside the snapshot, changing its file set. The correction normalizes destination journal mode and verifies finalized snapshots with immutable SQLite reads. A new WAL regression and the complete restore drill passed. Failed evidence remains in `restore_drill_wal_failure.log`; the initial incorrect script invocation is also retained separately.

Security scanning led to a pinned base refresh from Debian Bookworm to Trixie while retaining **Python 3.11.17** and existing numerical-library versions. The existing `opentelemetry-api` dependency received only the recommended **1.45.0 → 1.45.1** patch, with a package-specific exception to the historical release cutoff. Unused installed base pip/setuptools/wheel packages and their vendored copies were removed; application packages still come from the locked build-stage environment. The image includes no runtime Locust, pytest or vLLM.

Debian records the old SQLite version as affected and Trixie's version as fixed for [CVE-2025-7458](https://security-tracker.debian.org/tracker/CVE-2025-7458). The other old critical scanner entry concerned [MiniZip in zlib](https://security-tracker.debian.org/tracker/CVE-2023-45853); Debian explicitly notes the affected component was not built into the old binary packages. The report retains that distinction rather than claiming an exploited application vulnerability.

## Executed fault/security checks

The final clean Linux test image passed **669 tests, zero failures and zero skips**, in **367.29 seconds**, under 1 CPU/2 GiB/128 PIDs with no external network. Only the existing CollegeMsg input was mounted read-only for its ingestion checks. [Final output](evidence/regression_final.log), [JUnit](evidence/regression_final.xml), [acceptance and case matrix](evidence/acceptance.json).

The suite covers actual contained worker termination/checkpoint resume with exact clean parity, durable restart/idempotency, bounded local retries, immutable recovery envelopes, incomplete outputs, database unavailable/read-only failures, deadline termination, queue saturation and a memory-limited child failing without blind retry. Provider fixtures cover timeout, HTTP 429/503, permanent rejection, malformed/oversized output and retained uncertain reservations. Network-denied worker and broker boundaries, tenant ownership, trace/artifact access, framing/size/schema/path attacks, prompt injection, tool allowlists, answer-key isolation and browser session/origin controls also ran.

These are engineering fixture outcomes, not production reliability probabilities. The acceptance file's pass fraction describes the executed fixtures only. Memory exhaustion uses a bounded test child rather than forcing an uncontrolled host/container OOM. Provider faults are local fixtures; no hosted provider was called. Redis failure is inapplicable because this system has no Redis service. Physical power loss, multi-host failover and malicious arbitrary-code execution are not claimed as tested.

Earlier evidence is retained: 67 focused checks passed before the additional artifact fault; that fault then failed as expected with the old response and passed after correction. A pre-WAL-correction full run passed 667 tests, illustrating why the separate actual restore drill was necessary. The final image includes both additional WAL/memory checks and the complete corrected implementation.

## Backup, restoration and scientific consistency

The isolated synthetic drill completed a real mock community workflow, created a snapshot, renamed the source aside, restored to the same absolute state path and reopened the API. **All 24 restored files and all job columns matched exactly**, aggregate scientific results matched, another owner remained denied and replaying the original idempotency key created no new job or processing attempt. There were zero lost/duplicate jobs or corrupt artifacts in this drill. Restore took approximately **0.0034 seconds**, followed by **0.170 seconds** for the in-process restored API checks; these timings describe the tiny 426,087-byte fixture, not production recovery time. [Drill evidence](evidence/restore_drill.json), [final-image output](evidence/restore_final.log).

Before deployment, the idle service was stopped and its complete private state was backed up: **762 files, 17,822,088 bytes**, in **52.65 seconds**. A separately published private restored copy passed validation in **71.17 seconds** without starting an API or replacing the live volume. [Sanitized backup metadata](evidence/production_backup.json), [restore output](evidence/production_restore.log). The actual backup and restored files remain under `.secrets/phase7-backups/`; they contain private run/accounting material and must not be committed or uploaded.

After deployment, one explicit mock job returned the **exact complete minimized result** from the unchanged Phase 5 baseline. Its result and trace survived restart, all 18 capabilities were available, and **all columns of the 36 pre-existing job rows remained exact**. API charged spend stayed **$0.015085346000000001**; this is retained existing spend, not a charge from Phase 7. No old ledger was restored over the active database. [Deployed checks](evidence/deployment_verification.json), [parity result](evidence/parity_result.json), [pre-deployment metadata](evidence/pre_deploy.json).

The running image's 85 source/asset files exactly match local content. UID 10001, read-only root and binds, all dropped capabilities/no-new-privileges, localhost-only HTTPS, 1 CPU/2 GiB/128 PIDs, bounded logs and the original `blackgrid_blackgrid-state` volume were verified. The deployed/scanned image identity is **`sha256:fe87bd726b8c1366db1dc27ff22cd73fe8f6f565706c27678fe9426306fcdd58`**. Source remains on the existing uncommitted working tree; no commit, push or branch change was made.

Final headless Edge verification passed login, automatic live updates, cleared token input, desktop/mobile layout, sign-out revocation and the independently checked local certificate pin, with zero page errors or external page requests. No credentials, browser storage or HAR were exported. [Browser evidence](evidence/browser_verification.json), [desktop](evidence/dashboard-desktop.png), [mobile](evidence/dashboard-mobile.png).

## Vulnerability assessment and remaining risks

The official Trivy **0.76.0** scanner read a local image archive with no Docker socket, private state, provider credentials or image upload. Its public vulnerability database was updated **23 October 2026 at 07:12:39 UTC**. The final scan covered **87 OS packages and 59 Python packages**. Raw reports, archive/scan hashes, scanner digest, database timestamps and image identity are retained. [Final scan summary](evidence/scan_summary.json), [complete findings](evidence/scan_phase7.json), [unsuppressed advisory inventory](evidence/vulnerability_triage.json).

| Scanner finding instances | Previous image | Final image |
|---|---:|---:|
| Critical | 2 | **0** |
| High | 63 | **44** |
| Medium | 118 | **58** |
| Low | 108 | **61** |
| Unknown | 1 | **1** |
| Python package findings, all severities | 10 | **0** |

The final **164 OS finding instances represent 71 distinct advisories**. None had an available fixed distribution package according to this database. They are retained and not suppressed. The remaining high findings require continued patch review; zero critical/Python findings does not mean vulnerability-free software or a clean wider-release security gate. Older retained Phase 5/6 images are rollback/reproduction artifacts with known findings, not newly scanned release candidates. Scan coverage is metadata/advisory based and does not prove absence of unknown application/native-library vulnerabilities. [Trivy database documentation](https://trivy.dev/docs/dev/configuration/db/).

The scanner's first attempt exhausted its 128 MiB temporary mount while downloading a 129 MiB database. That failed scan was not treated as a pass; the retained retry used bounded 768 MiB temporary space and completed. No private information was uploaded.

## Cost, limitations and next step

New external provider calls: **0**. New provider spend: **$0**. Local container builds, scanner/database downloads, CPU/memory, local archives and private backup storage were used. No cloud/GPU resources, additional production services, paid load or external telemetry were introduced. The dashboard remains the existing live Phase 6 interface; Phase 7 adds recovery/security verification rather than a new performance feature.

Backups require all API/independent CLI writers stopped and the same absolute state path on restore. Manifest hashes provide integrity, not encryption or digital signatures. Windows-native backup semantics, physical-disk/power-loss recovery, sustained production reliability, real-provider outage recovery and public deployment are not established. CollegeMsg descriptive scope and scientific limitations remain unchanged; engineering parity is not new scientific validation.

The next smallest task, after separate approval, is Phase 8 profiling and measured optimization using a controlled workload. Keep the unsuppressed OS findings under review and re-scan when fixes are released. Do not start vLLM or later phases automatically.
