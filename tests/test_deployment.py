"""Deployment safety and lifecycle checks using tiny fixtures and zero providers."""
from __future__ import annotations

import hashlib
import json
import signal
import threading
from pathlib import Path

import pytest
from pydantic import ValidationError

from blackgrid.console.server import Console
from blackgrid.operations.__main__ import main
from blackgrid.operations.health import readiness
from blackgrid.operations.lifecycle import run_console
from blackgrid.operations.settings import Settings, load_settings
from tests.test_console import console as live_console, request

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings(tmp_path):
    data = tmp_path / "events.txt"
    data.write_text("1 2 100\n2 3 101\n", encoding="utf-8")
    config = json.loads((ROOT / "configs/collegemsg_sprint01.json").read_text())
    config["dataset"]["path"] = data.name
    config["dataset"]["sha256"] = hashlib.sha256(data.read_bytes()).hexdigest()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    runs = tmp_path / "runs"
    (runs / "cache").mkdir(parents=True)
    return Settings(config=config_path, data_root=tmp_path, runs_dir=runs)


@pytest.mark.parametrize("name,value", [("PORT", "0"), ("PORT", "65536"), ("ENV", "unknown"),
    ("SHUTDOWN_GRACE_SECONDS", "nan"), ("SHUTDOWN_GRACE_SECONDS", "-1"),
    ("CAPABILITIES", "shell"), ("CAPABILITIES", "")])
def test_invalid_environment_fails_before_service_start(name, value):
    with pytest.raises(ValidationError):
        load_settings({"BLACKGRID_" + name: value})


def test_readiness_checks_bytes_without_parsing_or_provider_calls(settings, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("readiness must not execute data analysis or a provider")
    monkeypatch.setattr("blackgrid.data.collegemsg.load_events", forbidden)
    monkeypatch.setattr("blackgrid.agent.providers.OpenRouterProvider.complete", forbidden)
    monkeypatch.setattr("blackgrid.agent.providers._http_json", forbidden)
    before = settings.config.read_bytes()
    assert readiness(settings, probe_server=False) == []
    assert settings.config.read_bytes() == before
    assert list(settings.cache_dir.iterdir()) == []
    (settings.data_root / "events.txt").write_text("changed")
    assert readiness(settings, probe_server=False) == ["dataset_checksum_mismatch"]


def test_readiness_rejects_unsafe_path_and_unavailable_evidence(settings):
    raw = json.loads(settings.config.read_bytes())
    raw["dataset"]["path"] = "../outside.txt"
    settings.config.write_text(json.dumps(raw))
    assert "dataset_path_outside_root" in readiness(settings, probe_server=False)
    expanded = settings.model_copy(update={"capabilities": ("forecast", "research"),
                                          "runs_dir": settings.runs_dir / "missing"})
    failures = readiness(expanded, probe_server=False)
    assert "state_unwritable" in failures and "required_evidence_unavailable" in failures


def test_readiness_rejects_live_config_and_corrupt_database(settings):
    raw = json.loads(settings.config.read_bytes())
    raw.update(mode="live", paid_execution_authorized=True)
    settings.config.write_text(json.dumps(raw))
    (settings.runs_dir / "workflow.sqlite").write_bytes(b"broken database")
    failures = readiness(settings, probe_server=False)
    assert "service_requires_mock_config" in failures and "state_database_unavailable" in failures


def test_launcher_validates_before_invoking_cli(settings, monkeypatch, capsys):
    monkeypatch.setenv("BLACKGRID_CONFIG", str(settings.config))
    monkeypatch.setenv("BLACKGRID_DATA_ROOT", str(settings.data_root))
    monkeypatch.setenv("BLACKGRID_RUNS_DIR", str(settings.runs_dir))
    calls = []
    monkeypatch.setattr("blackgrid.cli.main", lambda argv: calls.append(argv) or 0)
    assert main(["serve"]) == 0
    assert "--allow-paid" not in calls[0] and "--shutdown-grace-seconds" in calls[0]
    settings.config.write_text("not json")
    assert main(["serve"]) == 1 and len(calls) == 1
    assert "not json" not in capsys.readouterr().out


def test_drain_rejects_new_work_and_waits_for_started_action(settings, monkeypatch):
    con = Console(settings.runs_dir, settings.cache_dir, settings.config, settings.data_root, 8765)
    entered, release = threading.Event(), threading.Event()
    def work(argv):
        entered.set()
        release.wait(5)
        return 0
    monkeypatch.setattr("blackgrid.cli.main", work)
    job = con.start_job({"action": "pilot"})
    assert entered.wait(2)
    con.stop_admission()
    with pytest.raises(RuntimeError, match="shutting down"):
        con.start_job({"action": "pilot"})
    assert not con.drain(.01) and job["state"] == "running"
    release.set()
    assert con.drain(2) and job["state"] == "done" and con.busy is None


def test_sigterm_stops_admission_closes_listener_and_restores_handler(settings):
    con = Console(settings.runs_dir, settings.cache_dir, settings.config, settings.data_root, 8765)
    stopped = threading.Event()
    previous = signal.getsignal(signal.SIGTERM)
    class Server:
        closed = False
        def serve_forever(self):
            signal.raise_signal(signal.SIGTERM)
            assert stopped.wait(2)
        def shutdown(self):
            stopped.set()
        def server_close(self):
            self.closed = True
    server = Server()
    assert run_console(server, con, 1)
    assert con.stopping and server.closed and signal.getsignal(signal.SIGTERM) == previous


def test_local_health_obeys_host_guard_and_detects_shutdown(live_console, settings):
    from blackgrid.operations.health import alive
    local = settings.model_copy(update={"port": live_console.port})
    assert alive(local) and readiness(local) == []
    code, _, _ = request(live_console, "GET", "/health/live", host="foreign.example:80")
    assert code == 403
    live_console.stop_admission()
    assert not alive(local) and "server_unavailable" in readiness(local)


@pytest.mark.parametrize("payload", [[], {"status": "stopping"}])
def test_health_does_not_accept_unexpected_server_payload(settings, monkeypatch, payload):
    class Connection:
        status = 200
        def __init__(self, *args, **kwargs): pass
        def request(self, *args): pass
        def getresponse(self): return self
        def read(self, *args): return json.dumps(payload).encode()
        def close(self): pass
    monkeypatch.setattr("blackgrid.operations.health.http.client.HTTPConnection", Connection)
    from blackgrid.operations.health import alive
    assert not alive(settings)
