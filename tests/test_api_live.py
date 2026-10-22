"""Live API integration with fake pricing/completions; never contact a provider."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from contextlib import closing

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from blackgrid.operations.api import create_app
from blackgrid.operations.api_jobs import APIError, Jobs, Submission
from blackgrid.operations.live import LivePolicy, broker_request, receive, send
from tests.test_api import CREDS, headers
from tests.test_deployment import settings


@pytest.fixture
def policy(settings, monkeypatch):
    raw = json.loads(settings.config.read_bytes())
    raw.update(mode="live", paid_execution_authorized=True)
    raw["llm"] = {"model": "fixture/model", "max_tokens_per_call": 1000, "request_timeout_s": 5}
    path = settings.data_root / "live.json"
    path.write_text(json.dumps(raw))
    secret = settings.data_root / "key.txt"
    secret.write_text("synthetic-key-not-a-real-credential")
    result = LivePolicy(model="fixture/model", prior_spend_usd=.1, ceiling_project_usd=.5,
                        config=path, key_file=secret, subjects=("alice",))
    source = settings.data_root / "policy.json"
    source.write_text(result.model_dump_json())
    monkeypatch.setenv("BLACKGRID_API_LIVE_POLICY_FILE", str(source))
    return result


def test_explicit_request_authorization_and_mock_digest_compatibility():
    with pytest.raises(ValidationError):
        Submission(mode="live")
    with pytest.raises(ValidationError):
        Submission(allow_paid=True)
    assert Submission().model_dump_json() == '{"mode":"mock","scope":"first_window","condition":"validated","question":null}'
    assert Submission(mode="live", allow_paid=True).mode == "live"


def test_live_disabled_or_wrong_owner_cannot_launch(settings):
    jobs = Jobs(settings)
    try:
        with pytest.raises(APIError) as caught:
            jobs.submit("alice", "no-live", Submission(mode="live", allow_paid=True))
        assert caught.value.code == "live_not_authorized" and jobs.worker is None
    finally:
        jobs.close()


@pytest.mark.skipif(sys.platform != "linux", reason="live workers require Linux")
def test_reservation_survives_restart_and_is_not_renewed(settings, policy, monkeypatch):
    monkeypatch.setattr(Jobs, "work", lambda *args: None)
    jobs = Jobs(settings)
    body = Submission(mode="live", allow_paid=True)
    try:
        with pytest.raises(APIError) as denied:
            jobs.submit("bob", "same", body)
        assert denied.value.status == 403
        one, _ = jobs.submit("alice", "same", body)
        jobs.worker.join(2)
        two, created = jobs.submit("alice", "same", body)
        assert not created and one["job_id"] == two["job_id"]
        assert jobs.row("alice", one["job_id"])["reserved_usd"] == .15
    finally:
        jobs.close()
    jobs = Jobs(settings)
    try:
        same, created = jobs.submit("alice", "same", body)
        assert not created and same["state"] == "interrupted"
        jobs.submit("alice", "second", body)
        jobs.worker.join(2)
        with pytest.raises(APIError) as denied:
            jobs.submit("alice", "third", body)
        assert denied.value.code == "live_budget_exhausted"
        with closing(jobs.db()) as db:
            assert jobs.live_usage(db) == pytest.approx(.4)
    finally:
        jobs.close()


def test_broker_rejects_endpoints_models_and_bad_timeouts_before_transport(policy, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("transport must not run")
    monkeypatch.setattr("blackgrid.operations.live.subprocess.run", forbidden)
    cases = [dict(url="https://foreign.example", method="GET", timeout_s=5),
             dict(url="https://openrouter.ai/api/v1/chat/completions", method="POST", timeout_s=5,
                  body={"model": "different"}),
             dict(url="https://openrouter.ai/api/v1/models", method="GET", timeout_s=float("nan"))]
    for case in cases:
        assert broker_request(case, policy)["category"] == "permanent"


def test_broker_injects_secret_only_into_private_stdin(policy, monkeypatch):
    def transport(argv, **kwargs):
        payload = json.loads(kwargs["input"])
        assert "synthetic-key" not in " ".join(argv)
        assert payload["headers"]["Authorization"] == "Bearer " + policy.key()
        assert payload["deny_redirects"] is True
        assert set(payload["headers"]) == {"Authorization", "Content-Type", "X-Title"}
        return subprocess.CompletedProcess(argv, 0, b'{"ok":true,"response":{"data":[]}}')
    monkeypatch.setattr("blackgrid.operations.live.subprocess.run", transport)
    reply = broker_request(dict(url="https://openrouter.ai/api/v1/models", method="GET", timeout_s=5,
                                headers={"Authorization": "caller-selected"}), policy)
    assert reply["ok"]


@pytest.mark.skipif(sys.platform != "linux", reason="private FD and seccomp are Linux deployment controls")
def test_seccomp_worker_uses_inherited_broker_without_network(tmp_path):
    parent, child = socket.socketpair()
    def reply():
        request = receive(parent)
        assert request["url"] == "https://openrouter.ai/api/v1/models"
        send(parent, {"ok": True, "response": {"data": []}})
    thread = threading.Thread(target=reply)
    thread.start()
    source = '''from blackgrid.operations.worker import deny_network
deny_network()
from blackgrid.agent.providers import _http_json
assert _http_json("https://openrouter.ai/api/v1/models",timeout_s=5) == {"data":[]}
'''
    env = os.environ | {"BLACKGRID_PROVIDER_BROKER_FD": str(child.fileno())}
    try:
        result = subprocess.run([sys.executable, "-c", source], env=env, pass_fds=(child.fileno(),),
                                capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr.decode()
    finally:
        child.close(); parent.close(); thread.join(2)


@pytest.mark.skipif(sys.platform != "linux", reason="end-to-end live worker is a Linux container test")
@pytest.mark.parametrize("pricing_available", [True, False])
def test_complete_live_api_workflow_with_fake_provider(settings, policy, monkeypatch, pricing_available):
    import networkx as nx
    import hashlib
    from blackgrid.operations import live
    # Tiny synthetic graph, fixed reduced simulation counts; not a research benchmark.
    graph = nx.karate_club_graph()
    events = settings.data_root / "events.txt"
    events.write_text("".join(f"{a} {b} {100+i}\n" for i, (a,b) in enumerate(graph.edges())))
    for path in (settings.config, policy.config):
        raw = json.loads(path.read_bytes())
        raw["dataset"]["sha256"] = hashlib.sha256(events.read_bytes()).hexdigest()
        raw["experiment"].update(null_replicates=19, optimizer_restarts=1)
        raw["experiment"]["sensitivity"]["replicates"] = 1
        path.write_text(json.dumps(raw))
    calls = []
    def fake(payload, policy):
        calls.append(payload["method"])
        if payload["method"] == "GET":
            return {"ok": True, "response": {"data": [{"id": policy.model,
                "pricing": {"prompt": "0.0000001", "completion": "0.0000001"}}] if pricing_available else []}}
        plan = {"decision":"run", "reason":"Synthetic fixture", "tool_calls":[
            {"tool":"profile_graph","args":{}}, {"tool":"community_test","args":{"method":"louvain"}},
            {"tool":"edge_removal_sensitivity","args":{}}]}
        return {"ok": True, "response": {"model": policy.model, "choices":[{"message":{"content":json.dumps(plan)},
            "finish_reason":"stop"}], "usage":{"prompt_tokens":20,"completion_tokens":20,"cost":.000004}}}
    monkeypatch.setattr(live, "broker_request", fake)
    with TestClient(create_app(settings, CREDS), base_url="http://127.0.0.1") as client:
        response = client.post("/api/v1/jobs", json={"mode":"live","allow_paid":True}, headers=headers())
        assert response.status_code == 202, response.text
        job_id = response.json()["job_id"]
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            row = client.get(f"/api/v1/jobs/{job_id}", headers=headers()).json()
            if row["state"] not in ("queued","running"):
                break
            time.sleep(.4)
        app_jobs = client.app.state.jobs
        app_jobs.worker.join(3)
        stored = app_jobs.row("alice", job_id)
        if not pricing_available:
            assert row["state"] == "failed" and calls == ["GET"]
            assert stored["billing"] == "settled" and stored["charged_usd"] == 0
            assert stored["error_code"] == "pricing_unavailable"
            return
        assert row["state"] == "completed", row
        assert row["mode"] == "live" and row["progress"]["llm_calls"] >= 1
        assert stored["billing"] == "settled" and stored["charged_usd"] > 0
        assert "POST" in calls and calls[0] == "GET"
        folder = app_jobs.run_folder("alice", job_id)
        assert policy.key() not in (folder / "llm_trace.jsonl").read_text()
        assert client.post("/api/v1/jobs", json={"mode":"live","allow_paid":True}, headers=headers()).status_code == 200


def test_uncertain_provider_failure_keeps_full_reservation(settings, policy):
    jobs = Jobs(settings)
    try:
        job_id = "d" * 32
        folder = jobs.folder("alice", job_id)
        folder.mkdir(parents=True)
        with closing(jobs.db()) as db, db:
            db.execute("INSERT INTO jobs(id,owner,idem,digest,state,created,mode,reserved_usd,billing) VALUES(?,?,?,?,?,?,?,?,?)",
                (job_id,"alice","uncertain","digest","interrupted","fixture","live",.15,"reserved"))
        jobs.settle_live("alice", job_id, True, False)
        assert jobs.row("alice", job_id)["billing"] == "held"
        with closing(jobs.db()) as db:
            assert jobs.live_usage(db) == pytest.approx(.25)
    finally:
        jobs.close()


def test_api_transport_refuses_redirects_without_forwarding_key(monkeypatch):
    from blackgrid.agent import http_transport
    import urllib.error
    def build(handler):
        assert isinstance(handler, http_transport.NoRedirect)
        assert handler.redirect_request(None, None, 302, "redirect", {}, "https://foreign.example") is None
        class Opener:
            def open(self, req, timeout):
                raise urllib.error.HTTPError(req.full_url, 302, "redirect", {}, None)
        return Opener()
    monkeypatch.setattr(http_transport.urllib.request, "build_opener", build)
    reply = http_transport.request({"url":"https://openrouter.ai/api/v1/models", "method":"GET",
                                    "timeout_s":5, "deny_redirects":True})
    assert not reply["ok"] and reply["category"] == "permanent"
