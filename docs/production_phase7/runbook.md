# Incident response and private state recovery

Use the existing single-host service. Stop admission and preserve evidence before recovery; do not raise queue/worker limits or silently substitute scientific methods. Never blindly resubmit an uncertain paid request.

## First checks

Run `docker compose ps`, then the existing readiness command and `scripts/monitor_api.py`. Record stable error codes, job IDs, tool/stage, request/trace IDs and timestamps. Use `scripts/ask_api.py --job-id JOB_ID` for owner-scoped status/results and `scripts/monitor_api.py --trace JOB_ID` for its sanitized trace. Do not export credentials, questions, raw events, model responses, SQLite dumps or complete private run folders into tickets or public reports.

If database/storage readiness fails, stop new work and inspect disk space/permissions. Retain the current volume. A storage outage deliberately fails admission closed; restore storage, then restart only after checking active workers and paid reservations. Do not delete a database to make startup succeed. A generic container restart cannot repair corrupt scientific artifacts.

For `results_unavailable`, retain the job and original files. Verify snapshot hashes and the saved artifact receipts. The API refuses malformed/partial results; status alone does not prove downloadable results are intact. Do not edit a saved scientific report to make it pass. Restore a complete consistent snapshot to a separate volume for verification.

For `queue_full`/429, back off and reuse the original idempotency key when retrying admission. A rejected request has no durable job. For accepted work, keep the returned job ID; polling is preferable to a replacement submission. Queued mock work can recover automatically within its existing attempt/deadline limits; exhausted attempts and partial artifacts require inspection.

For provider timeout/network failure, `held`/uncertain billing or interrupted live work, keep the existing reservation. Reconcile the provider receipt and local operations ledger before any paid retry. Do not release unknown charges, reset the ledger, restore an older budget grant or enable an unrestricted endpoint. Provider 429/503 and malformed response fixtures in the test suite do not establish real provider availability.

For suspected access/credential compromise, stop the service, rotate the affected private token/key using the existing registry/policy procedure, retain the spend ledger and restart. Restart revokes browser sessions. Review owner isolation and sanitized traces. External publication, incident messages or third-party uploads require separate user direction.

## Backup contract

The module `python -m blackgrid.operations.backup` supports `create SOURCE NEW_DESTINATION`, `verify SNAPSHOT` and `restore SNAPSHOT NEW_DESTINATION`. It is an **offline API-state** tool: stop the API and all independent CLI writers first. It refuses an active service/execution lease, links/reparse points, corrupt databases, output within source, unsupported file types and the registered size/time/file caps. Snapshots include every regular authoritative artifact and standalone SQLite backups. Journal/lease files are not restored; WAL databases are normalized without changing logical records.

Keep snapshots under a private, non-synced location such as `.secrets/phase7-backups`, with a fresh timestamped destination. A snapshot may contain private questions/model traces and accounting; it is not a shareable benchmark report. The manifest supplies integrity hashes, not a digital signature or encryption. Protect its directory/backup medium and retain secrets/configuration separately under the existing private controls.

The module caps a snapshot at 4 GiB/100,000 files and each create/restore operation at 120 seconds. It publishes a new destination after validation/copy; failed staging is removed and existing destinations are never overwritten. These are filesystem rename semantics, not a tested power-loss durability guarantee. Windows-specific junction/permission behavior needs separate native verification before adopting this tool outside the tested Linux container deployment.

## Restore procedure

1. Stop admission, wait for active work, then stop the API. Retain the current image and volume. Record the current paid spend/reservations and snapshot identity privately.
2. Verify the chosen snapshot with the module. Restore to a **new empty destination/new volume**, never on top of the existing state. Keep the current paid ledger available for reconciliation.
3. Mount the restored state at the same absolute path (`/app/runs`) with the original config/data/evidence/registry bindings and restrictive container controls. Checkpoint run paths are bound to that location; this release does not migrate them to a different root.
4. Check database integrity, exact artifact hashes, all job/ledger fields and the saved aggregate results. Check ownership rejection and idempotent replay without creating replacement jobs. Mock interrupted jobs may resume only through existing checkpoint verification. Keep uncertain live jobs held for manual receipt reconciliation.
5. Check readiness, all tool capabilities and dashboard access. Start only one API writer per volume. Never run the original and restored volumes concurrently against a shared paid grant without reconciled accounting.
6. Switch the service's volume only after those checks and reconciliation. Preserve the previous volume for rollback. If restoration fails, retain its sanitized failure record and the original snapshot; do not merge arbitrary database/artifact files from different times.

The Phase 7 synthetic drill exercises create, verify, source removal by rename, restore, API restart, exact results/ledger fields, owner denial and idempotency. It does not erase production state or simulate a physical disk/power failure. Production state snapshots and provider credentials remain private.

## Vulnerability findings

Run `scripts/scan_phase7.py` against the current Phase 7 image to refresh the local image/OS/Python assessment. It uses the pinned official scanner, downloads its public database and reads a local archive; no private state, Docker socket or image upload is used. Retain raw findings, scanner/database timestamps, image/source identities and exceptions. Do not interpret zero critical findings as zero vulnerabilities. Re-scan after base/dependency changes and keep the high/medium findings visible. Review new fixed versions before a wider release.

Redis/distributed broker incidents do not apply: this deployment has neither. vLLM, load-based optimization, multi-host recovery and external security certification remain outside Phase 7.
