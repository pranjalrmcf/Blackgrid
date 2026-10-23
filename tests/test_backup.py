"""Offline snapshot invariants, actual SQLite state and reject-before-publish restore."""
import json
import sqlite3
from contextlib import closing
import pytest
from blackgrid.operations.backup import create,restore,verify,lease
from blackgrid.operations.api_jobs import Jobs,Submission
from tests.test_deployment import settings


def fixture_state(tmp_path):
    state = tmp_path/"state"
    (state/"api").mkdir(parents=True)
    with closing(sqlite3.connect(state/"api/jobs.sqlite")) as db,db:
        db.execute("create table jobs (id text, charged_usd real, billing text)")
        db.execute("insert into jobs values ('uncertain',0.02,'held')")
    (state/"report.json").write_text('{"verdict":"not_supported"}')
    return state


def test_snapshot_restores_database_artifact_and_held_spend_exactly(tmp_path):
    state = fixture_state(tmp_path)
    snapshot,dest = tmp_path/"snapshot",tmp_path/"restored"
    info = create(state,snapshot)
    assert info["files"] == 2
    before = verify(snapshot)
    restore(snapshot,dest)
    assert (dest/"report.json").read_bytes() == (state/"report.json").read_bytes()
    with closing(sqlite3.connect(dest/"api/jobs.sqlite")) as db:
        assert db.execute("select * from jobs").fetchall() == [('uncertain',.02,'held')]
    assert not (dest/"api/service.lock").exists()
    assert before == verify(snapshot)
    with pytest.raises(ValueError,match="must be new"): restore(snapshot,dest)
    with pytest.raises(ValueError): create(state,state/"nested")


@pytest.mark.parametrize("change", ["artifact","database","missing","extra","traversal","size"])
def test_bad_snapshot_never_publishes_destination(tmp_path,change):
    state = fixture_state(tmp_path)
    snapshot,dest = tmp_path/"snapshot",tmp_path/"restored"
    create(state,snapshot)
    if change in ("artifact","database"):
        (snapshot/("report.json" if change == "artifact" else "api/jobs.sqlite")).write_bytes(b"partial")
    elif change == "missing": (snapshot/"report.json").unlink()
    elif change == "extra": (snapshot/"unexpected").write_text("private")
    else:
        manifest = json.loads((snapshot/"snapshot.json").read_bytes())
        if change == "traversal": manifest["files"]["../outside"] = manifest["files"].pop("report.json")
        else: manifest["bytes"] += 1
        (snapshot/"snapshot.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError,OSError)): restore(snapshot,dest)
    assert not dest.exists()


def test_snapshot_refuses_active_api_and_orphan_worker_lease(tmp_path):
    state = fixture_state(tmp_path)
    with lease(state/"api/service.lock"):
        with pytest.raises(ValueError,match="state in use"): create(state,tmp_path/"active")
    lock = state/"api/execution.lock"
    with lease(lock):
        with pytest.raises(ValueError,match="state in use"): create(state,tmp_path/"orphan")


def test_corrupt_source_database_cannot_publish_snapshot(tmp_path):
    state = fixture_state(tmp_path)
    (state/"api/jobs.sqlite").write_bytes(b"torn database")
    with pytest.raises(ValueError): create(state,tmp_path/"snapshot")
    assert not (tmp_path/"snapshot").exists()


def test_wal_snapshot_stays_self_contained_across_repeated_verification(tmp_path):
    state = fixture_state(tmp_path)
    with closing(sqlite3.connect(state/'api/jobs.sqlite')) as db,db:
        assert db.execute('PRAGMA journal_mode=WAL').fetchone() == ('wal',)
        db.execute("insert into jobs values ('committed-in-wal',0.03,'settled')")
    snapshot = tmp_path/'snapshot'
    create(state,snapshot)
    assert verify(snapshot) == verify(snapshot)
    assert not list(snapshot.rglob('*-wal')) and not list(snapshot.rglob('*-shm'))
    restore(snapshot,tmp_path/'restored')
    with closing(sqlite3.connect(tmp_path/'restored/api/jobs.sqlite')) as db:
        assert db.execute('select count(*) from jobs').fetchone()[0] == 2


def test_snapshot_rejects_symlinks_instead_of_following_them(tmp_path):
    state = fixture_state(tmp_path)
    try: (state/"linked").symlink_to(tmp_path/"outside")
    except OSError: pytest.skip("symlink privilege unavailable")
    with pytest.raises(ValueError,match="link"): create(state,tmp_path/"snapshot")


def test_closed_api_state_restores_same_job_without_reexecution(settings,tmp_path,monkeypatch):
    monkeypatch.setattr(Jobs,"kick",lambda self:None)
    jobs = Jobs(settings)
    reply,_ = jobs.submit("alice","restore-fixture",Submission())
    job_id = reply["job_id"]
    jobs.state(job_id,"cancelled")
    original = dict(jobs.row("alice",job_id))
    jobs.close()
    snapshot,dest = tmp_path/"snapshot",tmp_path/"restored"
    create(settings.runs_dir,snapshot)
    restore(snapshot,dest)
    restored = Jobs(settings.model_copy(update={"runs_dir":dest}))
    try:
        assert dict(restored.row("alice",job_id)) == original
        replay,created = restored.submit("alice","restore-fixture",Submission())
        assert not created and replay["job_id"] == job_id and replay["state"] == "cancelled"
        with closing(restored.db()) as db: assert db.execute("select count(*) from jobs").fetchone()[0] == 1
    finally: restored.close()
