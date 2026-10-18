# Verification

## Applied repository verification — 18 October 2026

- Applied all eight prepared package files after baseline and package hashes passed.
  Replaced files are backed up in `ingestion-backup-20261018T094636329704Z/`.
- Ran `.venv/Scripts/python.exe -m blackgrid ingest configs/collegemsg_sprint01.json --data-root . --output runs/full-collegemsg-applied-v1`.
  The new JSON report equals the staged report below exactly, and its sidecar checksum verifies.
- Six focused ingestion tests passed, including CLI full-file coverage and overwrite refusal.
- Full regression suite passed: 192 tests in 101.42 seconds using approved execution
  outside the sandbox. The subsequent CLI regression addition passed in the six-test
  focused suite. Initial sandbox execution had 140 passes and 52 permission-related
  failures involving temporary-file replacement and loopback HTTP; the approved rerun
  resolved these without implementation changes.
- The raw input checksum still matches the frozen configuration. Historical loader,
  experiment, sensitivity, configuration and reference files match Git HEAD.
- No paid calls, new dependencies or external writes were needed.

## Earlier staged verification

Executed 18 October 2026 using Python 3.11.9 and NetworkX 3.6.1.

- Full CollegeMsg CLI ingestion completed against the original read-only local file.
- Input SHA-256 matched the existing frozen source configuration.
- 59,835 valid rows; 0 malformed; 37 exact duplicates retained and flagged.
- Aggregate report and its SHA-256 sidecar were written to a new staged directory.
- 5 ingestion tests passed: full-file coverage across weeks, duplicates, direction,
  self-loops, empty weeks, identifier-free output, report checksum, overwrite refusal,
  input tampering, malformed/empty data, rights rejection and path traversal rejection.
- Regression suite excluding `test_console.py`: 180 passed, 1 skipped, exit code 0.
  The skipped test requires the dataset under the staged repository, where raw data
  deliberately was not copied. Full-file ingestion was executed separately against
  the original path and checksum.
- Console tests could not run here: loopback HTTP access raises WinError 10013.
  This is a verification limitation; no console behavior was changed.
- Installer dry-run against `C:\Blackgrid`: all baseline checks passed. No files applied.

Only the `ingest` command was added to the existing CLI. Historical experiment,
projection, workflow and sensitivity implementation files were not changed.
No paid calls, credentials, raw data copies, commits or pushes were involved.

This verifies the full-data ingestion increment. Remaining Sprint 3 evaluation
and method-comparison work is not represented as complete.
