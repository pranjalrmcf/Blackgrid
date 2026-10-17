"""The offline entry point validates configs and records honest manifests for every outcome."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from blackgrid.cli import EXIT_INVALID, EXIT_OK, EXIT_RUN_FAILED, main
from blackgrid.contracts import RunManifest, RunStatus

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "collegemsg_sprint01.json"


def fixture_config(tmp_path: Path, events: str, sha: str | None = None) -> Path:
    data = tmp_path / "data" / "events.txt"
    data.parent.mkdir(parents=True)
    data.write_bytes(events.encode("utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["dataset"]["path"] = "data/events.txt"
    config["dataset"]["sha256"] = sha or hashlib.sha256(data.read_bytes()).hexdigest()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def run(tmp_path: Path, config: Path) -> tuple[int, Path, RunManifest]:
    runs = tmp_path / "runs"
    code = main(["run", str(config), "--runs-dir", str(runs), "--data-root", str(tmp_path)])
    (run_dir,) = runs.iterdir()
    manifest = RunManifest.model_validate_json((run_dir / "manifest.json").read_text(encoding="utf-8"))
    return code, run_dir, manifest


def test_validate_shipped_config(capsys):
    assert main(["validate", str(CONFIG)]) == EXIT_OK
    assert "valid" in capsys.readouterr().out


def test_validate_rejects_bad_config(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"mode": "live"}), encoding="utf-8")
    assert main(["validate", str(bad)]) == EXIT_INVALID


def test_run_builds_graph_then_stops_before_unimplemented_experiment(tmp_path):
    code, run_dir, manifest = run(tmp_path, fixture_config(tmp_path, "1 2 10\n2 3 20\n3 3 30\n"))
    assert code == EXIT_RUN_FAILED
    assert manifest.status is RunStatus.FAILED
    assert manifest.failure_reason.startswith("not_implemented: experiment")
    assert manifest.tool_calls[0].outcome == "completed"
    assert manifest.cost.actual_usd == 0 and manifest.cost.llm_calls == 0 and manifest.claims == ()
    for name, digest in manifest.artifacts.items():
        assert hashlib.sha256((run_dir / name).read_bytes()).hexdigest() == digest
    record = json.loads((run_dir / "graph_record.json").read_text(encoding="utf-8"))
    assert (record["active_nodes"], record["unique_edges"], record["self_loop_events_excluded"]) == (3, 2, 1)


def test_run_records_load_failure_on_checksum_mismatch(tmp_path):
    code, _, manifest = run(tmp_path, fixture_config(tmp_path, "1 2 10\n", sha="0" * 64))
    assert code == EXIT_RUN_FAILED
    assert manifest.failure_reason.startswith("load_failed: DataIntegrityError")
    assert manifest.tool_calls[0].outcome == "failed"


def test_run_records_window_abstention(tmp_path):
    events = "".join(f"0 {i} 0\n" for i in range(1, 1_001))
    code, run_dir, manifest = run(tmp_path, fixture_config(tmp_path, events))
    assert code == EXIT_RUN_FAILED
    assert manifest.status is RunStatus.ABSTAINED
    assert "graph_record.json" not in manifest.artifacts
    assert (run_dir / "window_selection.json").is_file()
