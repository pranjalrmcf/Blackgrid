"""Phase 4: bounded durable admission and recovery, with no paid/network calls."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from blackgrid.operations.api_jobs import APIError, Jobs, Submission
from tests.test_deployment import settings
from tests.test_api_live import policy


def wait_idle(jobs):
    if jobs.worker:
        jobs.worker.join(40)
        assert not jobs.worker.is_alive()
    assert not jobs.scheduler_failed


def enqueue_without_dispatch(settings, monkeypatch, count=1):
    with monkeypatch.context() as patch:
        patch.setattr(Jobs, "kick", lambda self: None)
        jobs = Jobs(settings)
        ids = [jobs.submit("alice", f"request-{i}", Submission())[0]["job_id"] for i in range(count)]
        jobs.close()
    return ids


def test_concurrent_unique_submissions_are_bounded_and_execute_once(settings, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls, active = [], []
    def work(self, owner, job, body):
        active.append(job)
        assert len(active) == 1
        calls.append(job)
        entered.set()
        release.wait(10)
        self.state(job, "completed")
        active.remove(job)
    monkeypatch.setattr(Jobs, "work", work)
    jobs = Jobs(settings)
    try:
        first, _ = jobs.submit("alice", "first", Submission())
        assert entered.wait(3)
        def submit(i):
            try:
                return jobs.submit("alice", f"parallel-{i}", Submission())[0]["job_id"]
            except APIError as exc:
                assert exc.code == "queue_full"
                return None
        with ThreadPoolExecutor(max_workers=12) as pool:
            accepted = [job for job in pool.map(submit, range(12)) if job]
        assert len(accepted) == 8
        release.set()
        wait_idle(jobs)
        assert len(calls) == len(set(calls)) == 9
        for job in [first["job_id"], *accepted]:
            row = jobs.row("alice", job)
            assert row["started"] and row["finished"] and row["attempts"] == 1
    finally:
        release.set()
        jobs.close()


def test_queued_request_survives_restart_with_same_identity(settings, monkeypatch):
    ids = enqueue_without_dispatch(settings, monkeypatch, 2)
    calls = []
    def work(self, owner, job, body):
        calls.append((job, body.model_dump_json()))
        self.state(job, "completed")
    monkeypatch.setattr(Jobs, "work", work)
    jobs = Jobs(settings)
    try:
        wait_idle(jobs)
        assert [job for job, _ in calls] == ids
        reply, created = jobs.submit("alice", "request-0", Submission())
        assert not created and reply["job_id"] == ids[0]
    finally:
        jobs.close()


def test_waiting_cancel_is_immediate_and_never_dispatched(settings, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(Jobs, "kick", lambda self: None)
        jobs = Jobs(settings)
        try:
            row, _ = jobs.submit("alice", "cancel-waiting", Submission())
            result = jobs.request_cancel("alice", row["job_id"])
            assert result["state"] == "cancelled" and result["completed_utc"]
            assert result["attempts"] == 0 and not result["started_utc"]
            with pytest.raises(APIError):
                jobs.request_cancel("bob", row["job_id"])
        finally:
            jobs.close()


def test_local_start_failures_retry_with_bounded_jitter_then_fail(settings, monkeypatch):
    calls, delays = [], []
    def failed(*args, **kwargs):
        calls.append(1)
        raise OSError("synthetic launch failure, private detail")
    def jitter(low, high):
        delays.append((low, high))
        return 0
    monkeypatch.setattr("blackgrid.operations.api_jobs.subprocess.Popen", failed)
    monkeypatch.setattr("blackgrid.operations.api_jobs.random.uniform", jitter)
    jobs = Jobs(settings)
    try:
        result, _ = jobs.submit("alice", "launch-failure", Submission())
        wait_idle(jobs)
        row = jobs.row("alice", result["job_id"])
        assert row["state"] == "failed" and row["error_code"] == "worker_start_failed"
        assert row["attempts"] == len(calls) == 3 and delays == [(0, 2), (0, 4)]
        assert "private detail" not in json.dumps(jobs.public(row))
    finally:
        jobs.close()


@pytest.mark.parametrize("change,expected", [("config", "invalid_recovery_envelope"),
    ("attempts", "recovery_limit_reached"), ("deadline", "recovery_limit_reached"),
    ("payload", "invalid_recovery_envelope"), ("digest", "invalid_recovery_envelope")])
def test_recovery_fails_closed_before_execution(settings, monkeypatch, change, expected):
    job, = enqueue_without_dispatch(settings, monkeypatch)
    database = settings.runs_dir / "api/jobs.sqlite"
    with sqlite3.connect(database) as db:
        if change == "config":
            db.execute("UPDATE jobs SET config_hash='changed'")
        elif change == "attempts":
            db.execute("UPDATE jobs SET attempts=3")
        elif change == "deadline":
            db.execute("UPDATE jobs SET deadline=1")
        elif change == "payload":
            db.execute("UPDATE jobs SET submission='invalid'")
        else:
            db.execute("UPDATE jobs SET submission=?", (Submission(question="Changed after acceptance").model_dump_json(),))
    monkeypatch.setattr(Jobs, "work", lambda *args: pytest.fail("unsafe job dispatched"))
    jobs = Jobs(settings)
    try:
        wait_idle(jobs)
        row = jobs.row("alice", job)
        assert row["state"] in ("failed", "timed_out") and row["error_code"] == expected
        assert row["attempts"] <= 3
    finally:
        jobs.close()


def test_partial_artifacts_do_not_start_a_second_run(settings, monkeypatch):
    job, = enqueue_without_dispatch(settings, monkeypatch)
    folder = settings.runs_dir / "api" / hashlib.sha256(b"alice").hexdigest() / job
    (folder / "partial-run").mkdir()
    (folder / "partial-run/config.json").write_text("{}")
    with sqlite3.connect(settings.runs_dir / "api/jobs.sqlite") as db:
        db.execute("UPDATE jobs SET state='running',attempts=1")
    jobs = Jobs(settings)
    try:
        wait_idle(jobs)
        row = jobs.row("alice", job)
        assert row["state"] == "failed" and row["error_code"] == "partial_artifacts_require_review"
        assert len(list(folder.glob("*/config.json"))) == 1
    finally:
        jobs.close()


def test_checkpoint_resume_matches_clean_run_without_second_manifest(settings, monkeypatch, tmp_path):
    from blackgrid.analysis.parity import compare, fingerprint
    from blackgrid.workflow.engine import SimulatedCrash
    from tests.test_workflow import Counting, start
    job, = enqueue_without_dispatch(settings, monkeypatch)
    folder = settings.runs_dir / "api" / hashlib.sha256(b"alice").hexdigest() / job
    with pytest.raises(SimulatedCrash):
        start(folder, Counting(), None, faults={"after_receipt:planner"})
    # No final manifest exists yet: recovery must use the authoritative runs table.
    assert not list(folder.glob("*/manifest.json"))
    with sqlite3.connect(settings.runs_dir / "api/jobs.sqlite") as db:
        db.execute("UPDATE jobs SET state='running',attempts=1")
    jobs = Jobs(settings)
    try:
        wait_idle(jobs)
        row = jobs.row("alice", job)
        assert row["state"] == "completed", row
        assert row["attempts"] == 2 and row["result_ref"].endswith("/results")
        clean = start(tmp_path / "reference", Counting(), None)
        recovered = jobs.run_folder("alice", job)
        assert compare(fingerprint(clean.run_dir), fingerprint(recovered)) == []
        assert len(list(folder.glob("*/manifest.json"))) == 1
    finally:
        jobs.close()


def test_database_failure_stops_admission_and_preserves_durable_queue(settings, monkeypatch):
    job, = enqueue_without_dispatch(settings, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(Jobs, "kick", lambda self: None)
        jobs = Jobs(settings)
    original = jobs.db
    def failed():
        raise sqlite3.OperationalError("synthetic storage unavailable")
    try:
        monkeypatch.setattr(jobs, "db", failed)
        jobs.dispatch()
        assert jobs.scheduler_failed
        monkeypatch.setattr(jobs, "db", original)
        with pytest.raises(APIError) as caught:
            jobs.submit("alice", "new", Submission())
        assert caught.value.code == "worker_unavailable"
        assert jobs.row("alice", job)["state"] == "queued"
    finally:
        jobs.close()


def test_idle_database_failure_makes_readiness_unavailable(settings, monkeypatch):
    from fastapi.testclient import TestClient
    from blackgrid.operations.api import create_app
    from tests.test_api import CREDS
    with TestClient(create_app(settings, CREDS), base_url="http://127.0.0.1") as client:
        def failed():
            raise sqlite3.OperationalError("private storage path")
        monkeypatch.setattr(client.app.state.jobs, "db", failed)
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["failures"] == ["job_scheduler_unavailable"]
        assert "private storage" not in response.text


def test_progress_contains_tool_and_analysis_without_arguments(settings, monkeypatch):
    from blackgrid.workflow.store import OperationStore
    from scripts.ask_api import tool_messages
    job, = enqueue_without_dispatch(settings, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(Jobs, "kick", lambda self: None)
        jobs = Jobs(settings)
    try:
        folder = jobs.folder("alice", job)
        with closing(OperationStore(folder / "workflow.sqlite")) as store:
            store.create_run("fixture", folder / "fixture", {})
            store.prepare("one", "fixture", "tool", "profile_graph", 0, 0, "hash", 0, 0)
            store.transition("one", "succeeded", records_json=json.dumps([{"private_node": "NEVER_EXPOSE"}]))
            store.prepare("two", "fixture", "tool", "community_test", 1, 0, "hash", 0, 0)
            store.transition("two", "dispatched")
        jobs.state(job, "running")
        progress = jobs.public(jobs.row("alice", job))["progress"]
        assert progress["current_tool"] == "community_test"
        assert "degree-preserving" in progress["analysis"]
        assert "NEVER_EXPOSE" not in json.dumps(progress)
        seen = {}
        lines = tool_messages(progress, seen)
        assert len(lines) == 2 and "profile_graph" in lines[0] and "Analysis:" in lines[1]
        assert tool_messages(progress, seen) == []
    finally:
        jobs.close()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux parent-death and worker lock controls")
def test_worker_lock_rejects_overlapping_recovery(tmp_path):
    path = tmp_path / "execution.lock"
    env = os.environ | {"BLACKGRID_JOB_LOCK_FILE": str(path)}
    source = "from blackgrid.operations.worker import execution_lease; lease=execution_lease()"
    import fcntl
    with path.open("a+b") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run([sys.executable, "-m", "blackgrid.operations.worker", "--help"], env=env, capture_output=True, timeout=10)
        assert result.returncode == 75
    result = subprocess.run([sys.executable, "-c", source], env=env, capture_output=True, timeout=10)
    assert result.returncode == 0


def test_execution_deadline_stops_child_and_is_not_retried(settings, monkeypatch):
    original = subprocess.Popen
    children = []
    def slow(argv, **kwargs):
        child = original([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr("blackgrid.operations.api_jobs.subprocess.Popen", slow)
    monkeypatch.setattr(Jobs, "EXECUTION_SECONDS", .3)
    jobs = Jobs(settings)
    try:
        result, _ = jobs.submit("alice", "deadline", Submission())
        wait_idle(jobs)
        row = jobs.row("alice", result["job_id"])
        assert row["state"] == "timed_out" and row["attempts"] == 1
        assert row["finished"] and children[0].poll() is not None and len(children) == 1
    finally:
        jobs.close()


@pytest.mark.skipif(sys.platform != "linux", reason="signal exit classification verified in Linux")
def test_real_worker_crash_after_receipt_resumes_with_exact_clean_parity(settings, monkeypatch):
    import networkx as nx
    from blackgrid.analysis.parity import compare, fingerprint
    events = settings.data_root / "events.txt"
    events.write_text("".join(f"{a} {b} {100+i}\n" for i, (a,b) in enumerate(nx.karate_club_graph().edges())))
    raw = json.loads(settings.config.read_bytes())
    raw["dataset"]["sha256"] = hashlib.sha256(events.read_bytes()).hexdigest()
    raw["experiment"].update(null_replicates=19, optimizer_restarts=1)
    raw["experiment"]["sensitivity"]["replicates"] = 1
    settings.config.write_text(json.dumps(raw))
    original = subprocess.Popen
    children = []
    def crash_first(argv, **kwargs):
        if not children:
            # Test-only fault: the genuine contained worker dies after persisting
            # a planner receipt, before checkpoint advancement/final artifacts.
            source = '''import os,signal
from blackgrid.workflow.engine import Runtime
original = Runtime.fault
def fault(self, point, qualifier=""):
    if point == "after_receipt" and qualifier == "planner":
        os.kill(os.getpid(), signal.SIGKILL)
    return original(self, point, qualifier)
Runtime.fault = fault
from blackgrid.operations.worker import main
raise SystemExit(main())
'''
            argv = [sys.executable, "-c", source, *argv[3:]]
        child = original(argv, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr("blackgrid.operations.api_jobs.subprocess.Popen", crash_first)
    monkeypatch.setattr("blackgrid.operations.api_jobs.random.uniform", lambda *args: 0)
    jobs = Jobs(settings)
    try:
        result, _ = jobs.submit("alice", "crash", Submission())
        wait_idle(jobs)
        row = jobs.row("alice", result["job_id"])
        assert row["state"] == "completed" and row["attempts"] == len(children) == 2, row
        assert len(list(jobs.folder("alice", row["id"]).glob("*/manifest.json"))) == 1
        recovered = fingerprint(jobs.run_folder("alice", row["id"]))
    finally:
        jobs.close()
    reference = Jobs(settings.model_copy(update={"runs_dir": settings.runs_dir / "reference"}))
    try:
        clean, _ = reference.submit("alice", "clean", Submission())
        wait_idle(reference)
        assert reference.row("alice", clean["job_id"])["state"] == "completed"
        assert compare(recovered, fingerprint(reference.run_folder("alice", clean["job_id"]))) == []
        assert recovered["llm_calls"] == 1
    finally:
        reference.close()


@pytest.mark.skipif(sys.platform != "linux", reason="live admission requires Linux")
def test_concurrent_live_reservations_cancel_and_interrupted_restart(settings, policy, monkeypatch):
    monkeypatch.setattr(Jobs, "kick", lambda self: None)
    jobs = Jobs(settings)
    body = Submission(mode="live", allow_paid=True)
    def submit(i):
        try:
            return jobs.submit("alice", f"live-{i}", body)[0]["job_id"]
        except APIError as exc:
            assert exc.code == "live_budget_exhausted"
            return None
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            ids = [job for job in pool.map(submit, range(8)) if job]
        assert len(ids) == 2
        cancelled = jobs.request_cancel("alice", ids[0])
        assert cancelled["state"] == "cancelled" and cancelled["progress"]["reserved_usd"] == 0
        with closing(jobs.db()) as db, db:
            db.execute("UPDATE jobs SET state='running',attempts=1 WHERE id=?", (ids[1],))
    finally:
        jobs.close()
    fresh = Jobs(settings)
    try:
        row = fresh.row("alice", ids[1])
        assert row["state"] == "interrupted" and row["billing"] == "held" and row["attempts"] == 1
        assert fresh.worker is None
        with closing(fresh.db()) as db:
            assert fresh.live_usage(db) == pytest.approx(.25)
    finally:
        fresh.close()


@pytest.mark.skipif(sys.platform != "linux", reason="live admission requires Linux")
def test_waiting_live_policy_change_fails_without_dispatch_and_releases_unused_hold(settings, policy, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(Jobs, "kick", lambda self: None)
        jobs = Jobs(settings)
        row, _ = jobs.submit("alice", "frozen-policy", Submission(mode="live", allow_paid=True))
    def forbidden(*args, **kwargs):
        raise AssertionError("changed authorization must not dispatch")
    monkeypatch.setattr("blackgrid.operations.api_jobs.subprocess.Popen", forbidden)
    raw = json.loads(policy.config.read_bytes())
    raw["llm"]["max_tokens_per_call"] = 999
    policy.config.write_text(json.dumps(raw))
    try:
        jobs.kick()
        wait_idle(jobs)
        stored = jobs.row("alice", row["job_id"])
        assert stored["state"] == "failed" and stored["error_code"] == "live_configuration_changed"
        assert stored["billing"] == "settled" and stored["charged_usd"] == 0
        assert jobs.public(stored)["progress"]["reserved_usd"] == 0
    finally:
        jobs.close()
