"""exp-v2-full: the opt-in full-dataset scope, kept separate from the frozen first-week experiment."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from blackgrid.cli import EXIT_OK, main
from blackgrid.collegemsg import build_bounded_graph, build_full_graph, build_graph
from blackgrid.contracts import RunConfig, RunManifest, RunStatus, WindowRule

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "configs" / "collegemsg_full.json"
WINDOW = ROOT / "configs" / "collegemsg_sprint01.json"
REAL = ROOT / "data" / "CollegeMsg.txt" / "CollegeMsg.txt"
DAY = 86_400


def config(path: Path, **changes) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) | changes


def spread_events(days: int = 30) -> str:
    """dev-001's edges spread over `days` days, so the first week holds only part of them."""
    from blackgrid.benchmark import dev_cases

    edges = list(dev_cases()["dev-001"].graph.edges())
    return "".join(f"{u} {v} {1_000 + i * (days * DAY // len(edges))}\n" for i, (u, v) in enumerate(edges))


def fixture(tmp_path: Path, base: Path, **changes) -> tuple[Path, dict]:
    data = tmp_path / "data" / "events.txt"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_bytes(spread_events().encode())
    cfg = config(base, **changes)
    cfg["dataset"] = cfg["dataset"] | {"path": "data/events.txt", "sha256": hashlib.sha256(data.read_bytes()).hexdigest()}
    return data, cfg


# --- contracts -----------------------------------------------------------------------------------


def test_shipped_configs_keep_the_scopes_separate():
    full = RunConfig.model_validate(config(FULL))
    window = RunConfig.model_validate(config(WINDOW))
    assert full.scope == "full_dataset" and window.scope == "first_window"
    assert full.experiment.graph_id == "collegemsg-full" and window.experiment.graph_id == "collegemsg-window"
    assert window.experiment.limits.within_first_window_limits()  # the historical experiment is unchanged
    assert window.sensitivity_null_replicates is None and window.experiment.null_replicates == 499


def test_full_limits_and_sensitivity_settings_need_the_full_scope():
    bad = config(FULL, scope="first_window")
    with pytest.raises(ValidationError, match="first-window runs keep the Sprint 1 limits"):
        RunConfig.model_validate(bad)
    bad = config(WINDOW, sensitivity_null_replicates=19)
    with pytest.raises(ValidationError, match="only configurable for scope=full_dataset"):
        RunConfig.model_validate(bad)


def test_full_graph_uses_every_event_and_the_window_graph_does_not(tmp_path):
    _, cfg = fixture(tmp_path, FULL)
    source = RunConfig.model_validate(cfg).dataset
    full = build_full_graph(tmp_path, source)
    window = build_bounded_graph(tmp_path, source, WindowRule())
    assert full.record.scope == "full_dataset" and full.selection is None
    assert full.record.window_events == full.record.raw_events == 97
    assert window.record.window_events < full.record.window_events  # the first week holds only part
    assert full.record.unique_edges == 97 and full.scope_artifact == "full_scope.json"
    assert build_graph(tmp_path, RunConfig.model_validate(cfg)).record.scope == "full_dataset"


def test_full_scope_record_rules():
    from blackgrid.contracts import GraphRecord

    _, cfg = None, config(FULL)
    base = dict(graph_id="g", origin="real_public", source=cfg["dataset"], scope="full_dataset",
                window_start_ts=0, window_end_ts=10, raw_events=10, window_events=10,
                self_loop_events_excluded=0, exact_duplicate_rows_flagged=0, active_nodes=5, unique_edges=4,
                edge_status_counts={"observed": 4}, projection_sha256="a" * 64)
    GraphRecord.model_validate(base)
    with pytest.raises(ValidationError, match="every valid event"):
        GraphRecord.model_validate(base | {"window_events": 9})
    with pytest.raises(ValidationError, match="size limits"):
        GraphRecord.model_validate(base | {"active_nodes": 5_001})
    with pytest.raises(ValidationError, match="size limits"):  # first-window caps still apply there
        GraphRecord.model_validate(base | {"scope": "first_window", "window_candidate_index": 0,
                                           "active_nodes": 1_001})


# --- end to end ------------------------------------------------------------------------------------


def test_cli_full_scope_run_completes_and_is_labelled(tmp_path):
    _, cfg = fixture(tmp_path, FULL)
    cfg["experiment"] = cfg["experiment"] | {"null_replicates": 19, "sensitivity": {
        "mechanism": "uniform", "removal_fraction": 0.1, "replicates": 2}}
    path = tmp_path / "full.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    runs = tmp_path / "runs"
    code = main(["run", str(path), "--runs-dir", str(runs), "--data-root", str(tmp_path), "--cache-dir",
                 str(tmp_path / "cache"), "--env-file", str(tmp_path / "absent.env")])
    (run_dir,) = [p for p in runs.iterdir() if p.is_dir()]
    manifest = RunManifest.model_validate_json((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert code == EXIT_OK and manifest.status is RunStatus.COMPLETED
    record = json.loads((run_dir / "graph_record.json").read_text(encoding="utf-8"))
    assert record["scope"] == "full_dataset" and record["window_events"] == record["raw_events"] == 97
    assert (run_dir / "full_scope.json").is_file() and not (run_dir / "window_selection.json").exists()
    sens = json.loads((run_dir / "sensitivity.json").read_text(encoding="utf-8"))
    assert sens["null_replicates_per_run"] == 19 and sens["replicates"] == 2  # the configured reduced sensitivity
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "exp-v2-full, exploratory" in report and "Full dataset: all 97 valid message events" in report
    assert "Exploratory, not confirmatory" in report
    assert "Exploratory verdict (exp-v2-full rule, not preregistered)" in report
    assert "Preregistered verdict" not in report  # only the first-week experiment was preregistered


@pytest.mark.skipif(not REAL.is_file(), reason="CollegeMsg raw file not present locally")
def test_real_full_graph_matches_the_ingestion_counts():
    built = build_full_graph(ROOT, RunConfig.model_validate(config(FULL)).dataset)
    r = built.record
    assert (r.raw_events, r.window_events, r.active_nodes, r.unique_edges) == (59_835, 59_835, 1_899, 13_838)
    assert r.exact_duplicate_rows_flagged == 37 and r.self_loop_events_excluded == 0
