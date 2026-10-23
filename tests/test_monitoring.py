"""Privacy, authorization, bounded telemetry and scientific execution invariants."""
from __future__ import annotations

import json
import sqlite3
import sys
import threading
import time
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blackgrid.operations import telemetry
from blackgrid.operations.api import Credentials, create_app
from blackgrid.operations.api_jobs import Jobs, Submission
from blackgrid.operations.monitoring import Monitoring, alerts
from tests.test_api import CREDS, headers
from tests.test_api_tools import environment, ask
from tests.test_api_live import policy
from tests.test_deployment import settings

OPS = Credentials(clients=tuple(c.model_copy(update={"operator": c.subject == "alice"}) for c in CREDS.clients))


def test_monitoring_requires_operator_and_traces_require_owner(settings, monkeypatch):
    monkeypatch.setattr(Jobs, "kick", lambda self: None)
    with TestClient(create_app(settings, OPS), base_url="http://127.0.0.1") as client:
        for route in ("metrics", "monitoring", "monitoring.json"):
            path = "/api/v1/" + route
            assert client.get(path).status_code == 401
            assert client.get(path, headers=headers("bob")).status_code == 403
            assert client.get(path, headers=headers()).status_code == 200
        result = client.post("/api/v1/jobs", json={"question": "PRIVATE QUESTION"}, headers=headers())
        job = result.json()["job_id"]
        path = f"/api/v1/jobs/{job}/trace"
        assert client.get(path, headers=headers("bob")).status_code == 404
        trace = client.get(path, headers=headers()).json()
        assert trace["available"] and trace["trace_id"] == job
        assert {s["request_id"] for s in trace["spans"]} == {result.headers["x-request-id"]}
        assert "PRIVATE QUESTION" not in json.dumps(trace)
        client.app.state.monitoring.cache_time = 0
        metrics = client.get("/api/v1/metrics", headers=headers()).text
        assert job not in metrics and "PRIVATE QUESTION" not in metrics
        assert "blackgrid_http_request_duration_seconds_bucket" in metrics
        assert "blackgrid_jobs{state=\"queued\"} 1" in metrics
        page = client.get("/api/v1/monitoring", headers=headers())
        assert page.headers["content-type"].startswith("text/html")
        assert "<script" not in page.text and "default-src 'none'" in page.headers["content-security-policy"]


def test_untrusted_paths_and_headers_do_not_enter_logs_or_metric_labels(settings, capsys):
    with TestClient(create_app(settings, OPS), base_url="http://127.0.0.1") as client:
        secret = "DO_NOT_LOG_THIS_SECRET"
        for i in range(10):
            client.get(f"/{secret}{i}", headers={"X-Request-ID": secret, "traceparent": secret})
        metrics = client.get("/api/v1/metrics", headers=headers()).text
        assert secret not in metrics
        assert secret not in capsys.readouterr().out
        assert len(client.app.state.monitoring.requests) <= 2


def test_bounded_trace_reader_rejects_tampered_content_and_partial_lines(tmp_path):
    context = telemetry.job_context(tmp_path, "alice", "a"*32)
    with telemetry.span("tool_call", context=context, tool="profile_graph"):
        pass
    path = tmp_path / "telemetry.jsonl"
    records = telemetry.read_spans(path)
    assert len(records) == 2
    bad = records[0] | {"tool": "PRIVATE SECRET"}
    with path.open("ab") as out:
        out.write((json.dumps(bad)+"\n{}").encode())
    assert telemetry.read_spans(path) == records
    path.write_bytes(b" " * telemetry.LIMIT)
    with telemetry.span("tool_call", context=context, tool="profile_graph"):
        pass
    assert path.stat().st_size == telemetry.LIMIT


def test_monitoring_write_failure_never_changes_trusted_execution(tmp_path, monkeypatch):
    context = telemetry.job_context(tmp_path, "alice", "b"*32)
    context["path"] = str(tmp_path / "missing" / "trace.jsonl")
    before = telemetry.WRITE_FAILURES
    with telemetry.span("agent_execution", context=context):
        result = 42
    assert result == 42 and telemetry.WRITE_FAILURES == before + 2
    with pytest.raises(ValueError, match="private error"):
        with telemetry.span("agent_execution", context=context):
            raise ValueError("private error")


def test_histograms_window_and_alerts_have_known_numerical_answers():
    monitoring = Monitoring()
    for status, duration in ((200, .01), (200, .1), (503, 2.)):
        monitoring.begin()
        monitoring.finish("/health/ready", status, duration)
    # Numerical histogram invariants, including cumulative buckets and exact sum/count.
    bins = monitoring.latencies["/health/ready"]
    assert bins[0] == 1 and bins[2] == 2 and bins[-2] == 3
    assert bins[-1] == pytest.approx(2.11) and monitoring.active == 0
    sample = dict(database_available=False, scheduler_available=False, jobs={"queued": 7},
        queue_oldest_seconds=121, llm={"errors": {"uncertain": 1}},
        api={"window_samples": 20, "error_fraction": .1}, budget_ceiling_usd=3,
        budget_used_usd=2.5, worker_peak_rss_bytes=2*1024**3,
        resources={"disk_free_bytes": 0},
        workflow_read_failures=1, telemetry_write_failures_process=0)
    assert all(a["firing"] for a in alerts(sample))


def test_durable_costs_holds_and_cancelled_jobs_survive_monitor_restart(settings, monkeypatch):
    monkeypatch.setattr(Jobs, "kick", lambda self: None)
    jobs = Jobs(settings)
    try:
        job, _ = jobs.submit("alice", "queued", Submission())
        with closing(jobs.db()) as db, db:
            db.execute("UPDATE jobs SET mode='live',billing='held',reserved_usd=.15,charged_usd=.01")
        first = Monitoring().snapshot(jobs)
        again = Monitoring().snapshot(jobs)
        assert first["reserved_or_held_usd"] == again["reserved_or_held_usd"] == .15
        assert first["settled_usd"] == again["settled_usd"] == 0
        assert first["charged_usd"] == .01
    finally:
        jobs.close()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux contained worker with fake provider, no paid calls")
def test_real_cross_process_trace_tokens_tools_cost_and_content_isolation(environment, capsys):
    configured, _, _ = environment
    with TestClient(create_app(configured, OPS), base_url="http://127.0.0.1") as client:
        status, result = ask(client, "Which nodes bridge communities, and are those rankings robust?", "traced")
        assert status["state"] == "completed"
        job = status["job_id"]
        trace = client.get(f"/api/v1/jobs/{job}/trace", headers=headers()).json()
        assert not trace["open_span_ids"]
        records = trace["spans"]
        names = {r["name"] for r in records}
        assert {"job_scheduling", "agent_execution", "llm_call", "provider_request", "tool_call", "artifact_persistence"} <= names
        execution = next(r for r in records if r["name"] == "agent_execution")
        for record in records:
            assert record["trace_id"] == job and record["request_id"]
            if record["name"] in ("llm_call", "tool_call", "artifact_persistence"):
                assert record["parent_span_id"] == execution["span_id"]
        snapshot = client.get("/api/v1/monitoring.json", headers=headers()).json()
        assert snapshot["llm"]["actual_or_assumed_usd"] == result["summary"]["actual_usd"]
        assert snapshot["llm"]["input_tokens"] == result["summary"]["tokens_in"]
        assert snapshot["llm"]["output_tokens"] == result["summary"]["tokens_out"]
        assert snapshot["llm"]["ttft_seconds"] is None
        assert snapshot["tool"] and all(s["seconds"] for s in snapshot["tool"].values())
        assert snapshot["worker_peak_rss_bytes"] > 0
        output = capsys.readouterr().out + json.dumps(snapshot) + json.dumps(trace)
        assert "1000001" not in output and "messages" not in output and "private-broker-managed" not in output
        assert '"analysis"' in output


def test_storage_failure_is_visible_without_losing_api_metrics(settings, monkeypatch):
    jobs = Jobs(settings)
    try:
        def fail():
            raise sqlite3.OperationalError("PRIVATE PATH")
        monkeypatch.setattr(jobs, "db", fail)
        monitor = Monitoring()
        snapshot = monitor.snapshot(jobs)
        assert not snapshot["database_available"] and not snapshot["scheduler_available"]
        assert not jobs.scheduler_failed, "a monitoring read cannot change dispatcher state"
        assert "PRIVATE PATH" not in monitor.prometheus(snapshot)
        assert any(a["name"] == "storage_unavailable" and a["firing"] for a in snapshot["alerts"])
    finally:
        jobs.close()


def test_durable_monitor_scan_does_not_block_request_counters(settings, monkeypatch):
    jobs = Jobs(settings)
    monitor = Monitoring()
    entered, release = threading.Event(), threading.Event()
    original = monitor._durable
    def slow(jobs):
        entered.set()
        release.wait(3)
        return original(jobs)
    monkeypatch.setattr(monitor, "_durable", slow)
    thread = threading.Thread(target=lambda: monitor.snapshot(jobs))
    try:
        thread.start()
        assert entered.wait(2)
        start = time.perf_counter()
        monitor.begin()
        monitor.finish("/health/live", 200, .001)
        assert time.perf_counter() - start < .2
    finally:
        release.set()
        thread.join(5)
        jobs.close()


def test_typed_rate_limit_signal_without_provider_body_or_real_network(tmp_path, monkeypatch):
    from blackgrid.agent.providers import _http_json, ProviderError
    monkeypatch.setenv("BLACKGRID_PROVIDER_BROKER_FD", "fixture")
    monkeypatch.setattr("blackgrid.operations.live.worker_request", lambda payload:
        {"ok": False, "category": "transient", "http_status": 429, "error": "PRIVATE PROVIDER ERROR"})
    context = telemetry.job_context(tmp_path, "alice", "c"*32)
    with telemetry.span("llm_call", context=context):
        with pytest.raises(ProviderError) as error:
            _http_json("https://openrouter.ai/api/v1/chat/completions", timeout_s=1, body={})
    assert error.value.category == "transient"
    spans = telemetry.read_spans(tmp_path / "telemetry.jsonl")
    assert sum(s["name"] == "provider_rate_limit" and s["event"] == "end" for s in spans) == 1
    assert "PRIVATE PROVIDER ERROR" not in json.dumps(spans)


def test_tool_timing_does_not_add_nested_work_twice(settings, monkeypatch):
    monkeypatch.setattr(Jobs, "kick", lambda self: None)
    jobs = Jobs(settings)
    try:
        job, _ = jobs.submit("alice", "nested", Submission())
        folder = jobs.folder("alice", job["job_id"])
        with sqlite3.connect(folder/"workflow.sqlite") as db:
            db.execute("CREATE TABLE operations(kind,name,state,category,attempt,prompt_tokens,completion_tokens,actual_usd,reserved_usd,records_json)")
            records = [{"tool": "community_test", "elapsed_s": 3},
                       {"tool": "edge_removal_sensitivity", "elapsed_s": 5}]
            db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?,?,?,?,?)", (
                "tool", "edge_removal_sensitivity", "succeeded", None, 0, 0, 0, 0, 0, json.dumps(records)))
        snapshot = Monitoring().snapshot(jobs)
        assert snapshot["tool"]["edge_removal_sensitivity"]["seconds"] == [5]
        assert snapshot["workflow_read_failures"] == 0
    finally:
        jobs.close()
