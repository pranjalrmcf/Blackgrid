"""Bounded local checks. Never instantiate a provider or execute an analysis."""
from __future__ import annotations

import hashlib
import http.client
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from blackgrid.contracts import ExecutionMode, RightsStatus, RunConfig
from blackgrid.operations.settings import ROOT, Settings


def alive(settings: Settings) -> bool:
    conn = http.client.HTTPConnection("127.0.0.1", settings.port, timeout=2)
    try:
        conn.request("GET", "/health/live")
        response = conn.getresponse()
        payload = json.loads(response.read(1024))
        return response.status == 200 and isinstance(payload, dict) and payload.get("status") == "live"
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        conn.close()


def readiness(settings: Settings, *, probe_server: bool = True) -> list[str]:
    """Return stable failure codes, never raw exception/input/identifier text.

    Data checksum verifies bytes without parsing events. Optional evidence presence
    checks do not replace the scientific consumers' own identity verification.
    """
    failures: list[str] = []
    if probe_server and not alive(settings):
        failures.append("server_unavailable")
    try:
        config = RunConfig.model_validate_json(settings.config.read_bytes())
        if config.mode is not ExecutionMode.MOCK or config.paid_execution_authorized:
            failures.append("service_requires_mock_config")
        if config.experiment is None:
            failures.append("experiment_missing")
        if config.dataset.rights_status is not RightsStatus.ACCEPTED_LOCAL_NONCOMMERCIAL:
            failures.append("dataset_rights_unaccepted")
        root = settings.data_root.resolve()
        path = (root / config.dataset.path).resolve()
        if not path.is_relative_to(root):
            failures.append("dataset_path_outside_root")
        else:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != config.dataset.sha256:
                failures.append("dataset_checksum_mismatch")
    except (OSError, ValueError):
        failures.append("config_or_dataset_unavailable")
    try:
        from blackgrid.console.render import template
        if "__BOOT__" not in template():
            failures.append("console_template_invalid")
    except (OSError, ValueError):
        failures.append("console_template_unavailable")
    for directory in (settings.runs_dir, settings.cache_dir):
        try:
            with tempfile.TemporaryFile(dir=directory):
                pass
        except OSError:
            failures.append("state_unwritable")
            break
    # Existing SQLite files are inspected read-only; absent files initialize lazily.
    for name in ("workflow.sqlite", "checkpoints.sqlite"):
        path = settings.runs_dir / name
        if path.exists():
            try:
                with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
                    if db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                        failures.append("state_database_invalid")
            except sqlite3.Error:
                failures.append("state_database_unavailable")
    evidence: list[Path] = []
    if "forecast" in settings.capabilities:
        evidence += [settings.runs_dir / "sprint6-v1" / "selection.json",
                     ROOT / "results" / "sprint06-v2" / "summary.json",
                     ROOT / "results" / "sprint06-v3-bitcoin" / "summary.json"]
    if "research" in settings.capabilities:
        evidence += [ROOT / "runs" / "sprint7-final" / "sprint7_manifest.json"]
    for path in evidence:
        try:
            if not isinstance(json.loads(path.read_bytes()), dict):
                raise ValueError
        except (OSError, ValueError):
            failures.append("required_evidence_unavailable")
            break
    return sorted(set(failures))
