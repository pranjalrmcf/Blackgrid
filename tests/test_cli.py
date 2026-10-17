"""The offline entry point validates configs and records honest failure manifests."""

from __future__ import annotations

import json
from pathlib import Path

from blackgrid.cli import EXIT_INVALID, EXIT_OK, EXIT_RUN_FAILED, main
from blackgrid.contracts import RunManifest, RunStatus

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "collegemsg_sprint01.json"


def test_validate_shipped_config(capsys):
    assert main(["validate", str(CONFIG)]) == EXIT_OK
    assert "valid" in capsys.readouterr().out


def test_validate_rejects_bad_config(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"mode": "live"}), encoding="utf-8")
    assert main(["validate", str(bad)]) == EXIT_INVALID


def test_run_records_failed_manifest_until_pipeline_exists(tmp_path):
    assert main(["run", str(CONFIG), "--runs-dir", str(tmp_path)]) == EXIT_RUN_FAILED
    (run_dir,) = tmp_path.iterdir()
    manifest = RunManifest.model_validate_json((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest.status is RunStatus.FAILED
    assert manifest.failure_reason.startswith("not_implemented")
    assert manifest.cost.actual_usd == 0 and manifest.cost.llm_calls == 0
    assert manifest.claims == ()
