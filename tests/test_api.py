"""API ownership, admission, malformed input and workflow integration."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from blackgrid.operations.api import Client, Credentials, Listener, Rates, create_app, load_credentials
from blackgrid.operations.api_jobs import APIError, Jobs, Submission
from tests.test_deployment import settings

TOKENS = {"alice": "a" * 43, "bob": "b" * 43}
CREDS = Credentials(clients=tuple(Client(subject=name, token_sha256=hashlib.sha256(token.encode()).hexdigest())
                                  for name, token in TOKENS.items()))


def headers(owner="alice", key="request-1"):
    return {"Authorization": "Bearer " + TOKENS[owner], "Idempotency-Key": key}


@pytest.fixture
def api(settings, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def work(self, owner, job_id, body):
        self.state(job_id, "running")
        entered.set()
        release.wait(10)
        self.state(job_id, "cancelled" if self.row(owner, job_id)["cancel"] else "completed")
    monkeypatch.setattr(Jobs, "work", work)
    app = create_app(settings, CREDS)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, app, entered, release
        release.set()


@pytest.mark.parametrize("authorization", [None, "Bearer wrong", "Basic abc", "Bearer " + "x" * 43])
def test_missing_and_wrong_auth_are_rejected(api, authorization):
    client, *_ = api
    h = {"Authorization": authorization} if authorization else {}
    reply = client.post("/api/v1/jobs", json={}, headers=h)
    assert reply.status_code == 401 and reply.headers["www-authenticate"] == "Bearer"
    assert reply.json()["error"]["code"] == "unauthorized"
    assert len(reply.headers["x-request-id"]) == 32
    assert "wrong" not in reply.text


def test_owner_boundaries_cover_status_cancel_results_and_artifacts(api):
    client, app, entered, release = api
    reply = client.post("/api/v1/jobs", json={}, headers=headers())
    assert reply.status_code == 202
    job = reply.json()["job_id"]
    assert entered.wait(3)
    for path in ("", "/results", "/artifacts/summary.json"):
        assert client.get(f"/api/v1/jobs/{job}{path}", headers=headers("bob")).status_code == 404
    assert client.post(f"/api/v1/jobs/{job}/cancel", json={}, headers=headers("bob")).status_code == 404
    assert not app.state.jobs.row("alice", job)["cancel"]
    assert client.get(f"/api/v1/jobs/{job}", headers=headers()).status_code == 200
    assert client.post(f"/api/v1/jobs/{job}/cancel", json={}, headers=headers()).json()["cancel_requested"]


def test_idempotency_replay_conflict_and_global_admission(api):
    client, app, entered, _ = api
    first = client.post("/api/v1/jobs", json={}, headers=headers())
    assert entered.wait(3)
    replay = client.post("/api/v1/jobs", json={}, headers=headers())
    assert replay.status_code == 200 and first.json()["job_id"] == replay.json()["job_id"]
    assert client.post("/api/v1/jobs", json={"condition": "tool_only"}, headers=headers()).status_code == 409
    assert client.post("/api/v1/jobs", json={}, headers=headers("bob")).status_code == 503


@pytest.mark.parametrize("body", [{"mode": "live"}, {"scope": "full_dataset"}, {"path": "../secret"},
    {"question": "x" * 501}, {"question": 123}, {"limits": {"max_nodes": 50000}}, [], "shell", {"condition": "x"}])
def test_invalid_requests_fail_without_worker(api, body):
    client, _, entered, _ = api
    reply = client.post("/api/v1/jobs", json=body, headers=headers())
    assert reply.status_code == 422 and not entered.is_set()
    assert reply.json()["error"]["code"] == "invalid_request"
    assert "secret" not in reply.text


def test_size_json_origin_host_methods_and_legacy_routes(api):
    client, *_ = api
    assert client.post("/api/v1/jobs", content=b"x" * 4097, headers=headers()).status_code == 413
    assert client.post("/api/v1/jobs", content=b"{", headers=headers() | {"Content-Type": "application/json"}).status_code == 422
    assert client.post("/api/v1/jobs", content="{}", headers=headers()).status_code == 415
    assert client.post("/api/v1/jobs", json={}, headers=headers() | {"Origin": "https://foreign.example"}).status_code == 403
    assert client.get("/health/live", headers={"Host": "foreign.example"}).status_code == 400
    assert client.delete("/health/live").status_code == 405
    for path in ("/", "/api/index", "/api/run", "/api/action", "/docs", "/openapi.json"):
        assert client.get(path, headers=headers()).status_code == 404
    assert client.get("/api/v1/openapi.json", headers=headers()).status_code == 200
    assert client.get("/api/v1/openapi.json").status_code == 401
    reply = client.get("/health/live")
    assert reply.headers["cache-control"] == "no-store"
    assert "access-control-allow-origin" not in reply.headers


def test_rate_limit_is_per_authenticated_subject(api):
    client, *_ = api
    responses = [client.get("/api/v1/openapi.json", headers=headers()).status_code for _ in range(65)]
    assert 429 in responses
    assert client.get("/api/v1/openapi.json", headers=headers("bob")).status_code == 200
    now = [0.0]
    rates = Rates(2, lambda: now[0])
    assert rates.allow("a") and rates.allow("a") and not rates.allow("a")
    now[0] = 30
    assert rates.allow("a")


def test_parallel_duplicate_and_restart_do_not_rerun(api, settings, monkeypatch):
    client, app, entered, release = api
    with ThreadPoolExecutor(max_workers=6) as pool:
        replies = list(pool.map(lambda _: client.post("/api/v1/jobs", json={}, headers=headers()), range(6)))
    assert sorted(r.status_code for r in replies) == [200] * 5 + [202]
    assert len({r.json()["job_id"] for r in replies}) == 1
    job = replies[0].json()["job_id"]
    release.set()
    app.state.jobs.worker.join(3)
    app.state.jobs.close()
    fresh = Jobs(settings)
    try:
        got, created = fresh.submit("alice", "request-1", Submission())
        assert not created and got["job_id"] == job
    finally:
        fresh.close()


def test_traversal_and_only_allowlisted_summary_artifact(api, settings):
    client, app, entered, release = api
    job = client.post("/api/v1/jobs", json={}, headers=headers()).json()["job_id"]
    for path in (f"/api/v1/jobs/{job}/artifacts/manifest.json", "/api/v1/jobs/..%2F..%2Fsecret",
                 f"/api/v1/jobs/{job}/artifacts/%2e%2e%2f.env"):
        assert client.get(path, headers=headers()).status_code == 404
    release.set(); app.state.jobs.worker.join(3)
    folder = app.state.jobs.folder("alice", job)
    assert folder.name == job and "alice" not in str(folder)
    try:
        folder.rmdir()
        folder.symlink_to(settings.data_root, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(APIError):
        app.state.jobs.folder("alice", job)


def test_credentials_fail_closed_and_external_listener_requires_tls(tmp_path):
    path = tmp_path / "clients.json"
    path.write_text('{"clients": []}')
    with pytest.raises(ValidationError):
        load_credentials(path)
    with pytest.raises(ValidationError):
        Credentials(clients=(CREDS.clients[0], CREDS.clients[0]))
    with pytest.raises(ValidationError):
        Listener(credentials_file=path, host="0.0.0.0")
    with pytest.raises(ValidationError):
        Listener(credentials_file=path, allowed_hosts=("*",))


def test_ambiguous_framing_duplicate_auth_and_duplicate_keys(api):
    client, *_ = api
    h = headers() | {"Content-Type": "application/json"}
    assert client.post("/api/v1/jobs", content=b'{}', headers=h | {"Content-Length": "1"}).status_code == 400
    assert client.post("/api/v1/jobs", content=b'{}', headers=h | {"Transfer-Encoding": "chunked"}).status_code == 411
    assert client.post("/api/v1/jobs", content=b'{"mode":"live","mode":"mock"}', headers=h).status_code == 422
    auth = [("Authorization", "Bearer " + TOKENS["alice"]), ("Authorization", "Bearer " + TOKENS["bob"])]
    assert client.get("/api/v1/openapi.json", headers=auth).status_code == 401


def test_interrupted_job_keeps_identity_and_second_process_is_rejected(settings):
    first = Jobs(settings)
    with pytest.raises(ValueError, match="already in use"):
        Jobs(settings)
    job = "c" * 32
    digest = hashlib.sha256(Submission().model_dump_json().encode()).hexdigest()
    with first.db() as db:
        db.execute("INSERT INTO jobs(id,owner,idem,digest,state,created) VALUES(?,?,?,?,?,?)",
                   (job, "alice", "interrupted-key", digest, "running", "2026-10-22T00:00:00Z"))
    first.close()
    second = Jobs(settings)
    try:
        result, created = second.submit("alice", "interrupted-key", Submission())
        assert not created and result["state"] == "interrupted" and result["job_id"] == job
    finally:
        second.close()


def test_aggregate_download_excludes_private_fields(api):
    client, app, _, release = api
    job = client.post("/api/v1/jobs", json={}, headers=headers()).json()["job_id"]
    release.set(); app.state.jobs.worker.join(3)
    run = app.state.jobs.folder("alice", job) / "20261022T000000Z-fixture"
    run.mkdir()
    (run / "manifest.json").write_text('{"status":"completed"}')
    (run / "investigation.json").write_text(json.dumps({"status": "completed", "verdict": "not_supported",
        "secret": "DO_NOT_EXPOSE", "reported_claims": [{"text": "PRIVATE_NODE_ID"}]}))
    reply = client.get(f"/api/v1/jobs/{job}/artifacts/summary.json", headers=headers())
    assert reply.status_code == 200 and "attachment" in reply.headers["content-disposition"]
    assert "DO_NOT_EXPOSE" not in reply.text and "PRIVATE_NODE_ID" not in reply.text
    assert "source_revision" not in reply.text and "data_root" not in reply.text


def test_tiny_offline_workflow_through_real_api(settings):
    # No workflow stub: tiny known-answer data abstains under the unchanged method gates.
    with TestClient(create_app(settings, CREDS), base_url="http://127.0.0.1") as client:
        job = client.post("/api/v1/jobs", json={}, headers=headers()).json()["job_id"]
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            row = client.get(f"/api/v1/jobs/{job}", headers=headers()).json()
            if row["state"] not in ("queued", "running"):
                break
            time.sleep(.3)
        assert row["state"] in ("completed", "abstained"), row
        reply = client.get("/health/ready")
        assert reply.status_code == 200 and reply.json()["status"] == "ready"


def test_cancel_reuses_existing_authoritative_flag(settings):
    from blackgrid.workflow.store import OperationStore
    jobs = Jobs(settings)
    try:
        folder = jobs.root / "cancel-fixture"
        folder.mkdir()
        store = OperationStore(folder / "workflow.sqlite")
        try:
            store.create_run("test-run", folder / "test-run", {"kind": "fixture"})
            jobs.cancel_workflow(folder)
            assert store.run("test-run")["cancel_requested"] == 1
        finally:
            store.close()
    finally:
        jobs.close()


def test_changed_config_rejected_before_launch(settings, monkeypatch):
    jobs = Jobs(settings)
    try:
        settings.config.write_text('{}')
        with pytest.raises(APIError) as caught:
            jobs.submit("alice", "changed", Submission())
        assert caught.value.status == 503 and caught.value.code == "configuration_changed"
        assert jobs.worker is None
    finally:
        jobs.close()
