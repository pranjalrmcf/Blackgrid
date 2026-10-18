"""End-to-end CLI behaviour on small local fixtures (offline, mock mode)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from blackgrid.cli import EXIT_INVALID, EXIT_OK, EXIT_RUN_FAILED, main
from blackgrid.contracts import RunManifest, RunStatus

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "collegemsg_sprint01.json"


def fixture_config(tmp_path: Path, events: str, sha: str | None = None, **overrides) -> Path:
    data = tmp_path / "data" / "events.txt"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_bytes(events.encode("utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["dataset"]["path"] = "data/events.txt"
    config["dataset"]["sha256"] = sha or hashlib.sha256(data.read_bytes()).hexdigest()
    config["experiment"] |= {"null_replicates": 19, "sensitivity": {"mechanism": "uniform", "removal_fraction": 0.1,
                                                                   "replicates": 2}}
    config |= overrides
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def run(tmp_path: Path, config: Path, *extra: str) -> tuple[int, Path | None, RunManifest | None]:
    runs = tmp_path / "runs"
    code = main(["run", str(config), "--runs-dir", str(runs), "--data-root", str(tmp_path),
                 "--cache-dir", str(tmp_path / "cache"), "--env-file", str(tmp_path / "absent.env"), *extra])
    dirs = sorted(p for p in runs.iterdir() if p.is_dir()) if runs.is_dir() else []
    if not dirs:
        return code, None, None
    run_dir = dirs[-1]
    manifest = run_dir / "manifest.json"
    return code, run_dir, (RunManifest.model_validate_json(manifest.read_text(encoding="utf-8"))
                           if manifest.is_file() else None)


def planted_events() -> str:
    from blackgrid.evaluation.benchmark import dev_cases

    graph = dev_cases()["dev-001"].graph
    return "".join(f"{u} {v} {1000 + i}\n" for i, (u, v) in enumerate(graph.edges()))


def test_validate_shipped_config(capsys):
    assert main(["validate", str(CONFIG)]) == EXIT_OK
    assert "valid" in capsys.readouterr().out


def test_validate_rejects_bad_config(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"mode": "live"}), encoding="utf-8")
    assert main(["validate", str(bad)]) == EXIT_INVALID


def test_full_mock_investigation_completes_with_linked_artifacts(tmp_path):
    code, run_dir, manifest = run(tmp_path, fixture_config(tmp_path, planted_events()))
    assert code == EXIT_OK and manifest.status is RunStatus.COMPLETED
    for name, digest in manifest.artifacts.items():
        assert hashlib.sha256((run_dir / name).read_bytes()).hexdigest() == digest, name
    for claim in manifest.claims:  # every manifest claim links to a real artifact hash
        for link in claim.evidence:
            assert manifest.artifacts[link.artifact] == link.sha256
    assert manifest.cost.actual_usd == 0 and manifest.cost.llm_calls >= 2
    assert (run_dir / "report.md").is_file() and (run_dir / "report.html").is_file()
    assert (tmp_path / "runs" / "index.html").is_file()
    inv = json.loads((run_dir / "investigation.json").read_text(encoding="utf-8"))
    assert inv["verdict"] == "supported"


def test_tiny_graph_experiment_abstains(tmp_path):
    code, run_dir, manifest = run(tmp_path, fixture_config(tmp_path, "1 2 10\n2 3 20\n3 3 30\n"))
    assert code == EXIT_RUN_FAILED and manifest.status is RunStatus.ABSTAINED
    assert "S1" in manifest.failure_reason
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "abstain" in report


def test_checksum_mismatch_fails_before_investigation(tmp_path):
    code, _, manifest = run(tmp_path, fixture_config(tmp_path, "1 2 10\n", sha="0" * 64))
    assert code == EXIT_RUN_FAILED and manifest.failure_reason.startswith("load_failed: DataIntegrityError")


def test_window_abstention(tmp_path):
    events = "".join(f"0 {i} 0\n" for i in range(1, 1_001))
    code, run_dir, manifest = run(tmp_path, fixture_config(tmp_path, events))
    assert code == EXIT_RUN_FAILED and manifest.status is RunStatus.ABSTAINED
    assert (run_dir / "window_selection.json").is_file()


def test_live_mode_gates_pause_before_any_paid_call_and_deny_is_visible(tmp_path, capsys):
    from blackgrid.cli import EXIT_PAUSED

    config = fixture_config(tmp_path, planted_events())
    assert run(tmp_path, config, "--mode", "live")[0] == EXIT_INVALID  # config lacks paid authorization
    live = fixture_config(tmp_path, planted_events(), mode="live", paid_execution_authorized=True)
    code, run_dir, manifest = run(tmp_path, live)  # config allows paid mode, but this run is not authorized
    assert code == EXIT_PAUSED and manifest is None
    assert "--allow-paid" in capsys.readouterr().err
    status = json.loads((run_dir / "workflow_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "paused" and status["pause"]["kind"] == "authorization"
    assert not (run_dir / "ops").exists()  # no provider call was prepared or dispatched
    runs = str(tmp_path / "runs")
    assert main(["deny", run_dir.name, "--runs-dir", runs, "--cache-dir", str(tmp_path / "cache")]) == EXIT_RUN_FAILED
    manifest = RunManifest.model_validate_json((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest.status is RunStatus.DENIED and manifest.cost.llm_calls == 0


def test_model_name_comes_from_env_file_in_live_mode_only(tmp_path, monkeypatch):
    from blackgrid.contracts import RunConfig
    from blackgrid.workflow.runner import apply_env_model

    for name in ("OPEN_ROUTER_MODEL", "OPENROUTER_MODEL"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / ".env"
    env.write_text("OPEN_ROUTER_API_KEY=sk-test\nOPEN_ROUTER_MODEL=vendor/some-model\n", encoding="utf-8")
    base = json.loads(CONFIG.read_text(encoding="utf-8"))
    live = RunConfig.model_validate(base | {"mode": "live", "paid_execution_authorized": True})
    assert apply_env_model(live, env).llm.model == "vendor/some-model"
    mock = RunConfig.model_validate(base)
    assert apply_env_model(mock, env).llm.model == mock.llm.model  # mock never reads .env


def test_replay_reproduces_a_mock_run(tmp_path):
    config = fixture_config(tmp_path, planted_events())
    _, first_dir, first = run(tmp_path, config)
    code, second_dir, second = run(tmp_path, config, "--mode", "replay", "--replay-from", str(first_dir))
    assert code == EXIT_OK and second_dir != first_dir
    a = json.loads((first_dir / "investigation.json").read_text(encoding="utf-8"))
    b = json.loads((second_dir / "investigation.json").read_text(encoding="utf-8"))
    assert (a["verdict"], a["reported_claims"]) == (b["verdict"], b["reported_claims"])


def test_tool_only_condition_reports_unreviewed_claims(tmp_path):
    code, run_dir, manifest = run(tmp_path, fixture_config(tmp_path, planted_events()), "--condition", "tool_only")
    inv = json.loads((run_dir / "investigation.json").read_text(encoding="utf-8"))
    assert inv["condition"] == "tool_only" and inv["critic_decisions"] == []
    assert manifest.claims == ()  # unreviewed claims never become manifest claims
    assert "NOT validated" in (run_dir / "report.md").read_text(encoding="utf-8")
