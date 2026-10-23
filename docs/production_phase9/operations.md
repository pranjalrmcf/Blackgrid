# Operations handbook

Operate one API writer on one local state volume. The deployed container is non-root UID/GID 10001, read-only root, dropped capabilities, no-new-privileges, localhost TLS, 1 CPU, 2 GiB and 128 PIDs. One analysis runs at a time and eight may wait. Ten clients do not mean ten parallel analyses. Do not share SQLite, grants or state across replicas/hosts. Independent paid CLI use must not overlap API use.

## Installation and configuration

Use Python 3.11, the frozen `uv.lock` and the pinned Dockerfile. Follow the [existing deployment instructions](../deployment.md), [API contract](../api.md), [live setup](../api_live.md) and [release commands](README.md). Keep the existing local data/evidence/config paths and grants; never download substitute data or recreate a spending grant to bypass exhaustion. Raw CollegeMsg has no redistribution authorization. A new host needs independently reviewed input/evidence availability and private TLS/credential provisioning; the repository does not contain those assets.

Compose fails on missing read-only bindings. Environment labels do not relax authentication, containment or scientific/budget checks. A mock-only installation must omit live-policy/key bindings rather than invent a grant. No secrets are build arguments or CI secrets. The production image excludes pytest, Locust, Ruff, mypy and vLLM. Only verification images contain test tools.

## Monitoring and incidents

Use the live operator dashboard and `scripts/monitor_api.py` for service/resource/job/tool/provider metrics and owner-scoped traces. The command-line client shows the analysis being executed and verified cache hits. Check readiness and stable error codes before restarting. Alerts are local, authenticated, polling-based diagnostics; no paging service or production availability history is claimed. The full regression tests verify queue/storage failure alerts and authorization, not just dashboard rendering.

For 429 `queue_full`, back off; retain the original idempotency key. For accepted work, poll the original job instead of submitting a replacement. For storage failure or corrupted artifacts, stop admission, preserve current state and restore to a separate destination for verification. For provider timeouts or uncertain billing, retain reservations and reconcile provider receipts before retrying. Do not reset a ledger or force-unlock an active process. See the [incident/restore runbook](../production_phase7/runbook.md) for exact procedures.

## Backup and recovery

Stop the API and all independent writers before using `python -m blackgrid.operations.backup create SOURCE NEW_DESTINATION`. Keep snapshots private and separate from the application state. Verify with `verify SNAPSHOT`; restore with `restore SNAPSHOT NEW_DESTINATION`. Never overwrite the current volume, restore an older spend balance over newer calls, combine artifacts from different snapshots or relocate checkpoint roots without a migration. Snapshot manifests detect integrity changes; they are neither encryption nor a digital signature. Protect backup media and retain credentials separately.

The tested synthetic restore uses the same absolute root, compares all artifact hashes and job columns, then checks exact results, ownership and idempotency. The production promotion makes a private offline snapshot and verifies existing records. These checks do not simulate power loss, filesystem corruption across a fleet, or uncertain real-provider settlement. Native Windows backup behavior outside the tested Linux container remains unvalidated.

## Upgrades, rollback and migrations

Phase 9 changes the application version to 1.0.0 and adds release controls; it adds no database columns or scientific algorithm changes. Existing additive schema initialization is unchanged and repeat startup is checked for schema stability. Keep the previous immutable image and a consistent private snapshot before every upgrade. The production rollback drill selects the previous Phase 8 image with the current state and returns to Phase 9, comparing every job column/spend/result. This proves this specific backward-compatible pair, not arbitrary future schema downgrades.

Future incompatible migrations must ship a separately tested forward conversion, compatibility window and rollback/reconciliation procedure before promotion. A failed deployment does not authorize restoring old paid records. Inspect and preserve the original volume; the pipeline does not blindly roll back data on failure.

## Capacity, retention and security maintenance

Keep current limits until a new protocol measures a different workload. Check queue wait as well as HTTP latency. Do not enable Kubernetes, distributed brokers or multiple workers from these short benchmarks. Tool cache retention is 512 files/128 MiB/seven days before/after a job, with an 8 MiB per-entry bound; transient in-job growth is possible. Invalid/unavailable entries recompute, and owner/mode/configuration/implementation changes separate namespaces. LLM outputs and paid calls are not cached. Bound private backup/benchmark retention operationally after reconciliation; do not delete current authoritative state to free space.

Refresh the exact-image scanner/database after any base/dependency change. Critical or fixable high findings block promotion. Existing unfixed OS highs are visible only under restricted local scope; public scope is blocked. Review new fixes instead of suppressing findings. Never expose localhost TLS service publicly or change secrets to make a CI test pass. The repository owner must separately configure protected branches and release-review protection; no account settings are silently changed by these workflows.
