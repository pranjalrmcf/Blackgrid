"""Single-host API admission and ownership around the existing trusted CLI."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from blackgrid.contracts import Contract
from blackgrid.operations.settings import ROOT, Settings


class Submission(Contract):
    mode: Literal["mock"] = "mock"
    scope: Literal["first_window"] = "first_window"
    condition: Literal["validated", "tool_only"] = "validated"
    question: str | None = Field(default=None, min_length=1, max_length=500)


class APIError(Exception):
    def __init__(self, status: int, code: str):
        self.status, self.code = status, code


class Jobs:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.config_sha256 = hashlib.sha256(settings.config.read_bytes()).hexdigest()
        self.root = settings.runs_dir / "api"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink():
            raise ValueError("unsafe API state")
        self.lock = threading.RLock()
        self.stopping = False
        self.worker: threading.Thread | None = None
        self.process: subprocess.Popen | None = None
        if any((self.root / name).is_symlink() for name in ("jobs.sqlite", "service.lock")):
            raise ValueError("unsafe API state")
        self._lease = (self.root / "service.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                self._lease.write(b"0"); self._lease.flush(); self._lease.seek(0)
                msvcrt.locking(self._lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lease.close()
            raise ValueError("API state already in use") from None
        with closing(self.db()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, owner TEXT NOT NULL, idem TEXT NOT NULL, digest TEXT NOT NULL,
                state TEXT NOT NULL, created TEXT NOT NULL, cancel INTEGER NOT NULL DEFAULT 0,
                UNIQUE(owner, idem))""")
            db.execute("UPDATE jobs SET state='interrupted' WHERE state IN ('queued','running')")

    def db(self):
        return sqlite3.connect(self.root / "jobs.sqlite", timeout=5)

    def row(self, owner: str, job_id: str) -> dict:
        with closing(self.db()) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM jobs WHERE owner=? AND id=?", (owner, job_id)).fetchone()
        if row is None:
            raise APIError(404, "not_found")
        return dict(row)

    def public(self, row: dict) -> dict:
        return {"job_id": row["id"], "state": row["state"], "created_utc": row["created"],
                "cancel_requested": bool(row["cancel"])}

    def folder(self, owner: str, job_id: str) -> Path:
        # Only server-generated IDs and digested credential subjects reach paths.
        folder = self.root / hashlib.sha256(owner.encode()).hexdigest() / job_id
        current = folder
        while current != self.root:
            if current.is_symlink():
                raise APIError(404, "not_found")
            current = current.parent
        if not folder.resolve().is_relative_to(self.root.resolve()):
            raise APIError(404, "not_found")
        return folder

    def submit(self, owner: str, idem: str, body: Submission) -> tuple[dict, bool]:
        digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
        with self.lock:
            with closing(self.db()) as db:
                found = db.execute("SELECT id,digest FROM jobs WHERE owner=? AND idem=?", (owner, idem)).fetchone()
                if found:
                    if found[1] != digest:
                        raise APIError(409, "idempotency_conflict")
                    return self.public(self.row(owner, found[0])), False
                if self.stopping or (self.worker and self.worker.is_alive()):
                    raise APIError(503, "worker_unavailable")
                if hashlib.sha256(self.settings.config.read_bytes()).hexdigest() != self.config_sha256:
                    raise APIError(503, "configuration_changed")
                if db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] >= 5000:
                    raise APIError(503, "job_capacity_reached")
                job_id = uuid.uuid4().hex
                folder = self.folder(owner, job_id)
                folder.parent.mkdir(exist_ok=True, mode=0o700)
                folder.mkdir(mode=0o700)
                db.execute("INSERT INTO jobs (id,owner,idem,digest,state,created) VALUES (?,?,?,?,?,?)",
                           (job_id, owner, idem, digest, "queued", datetime.now(UTC).isoformat()))
                db.commit()
            self.worker = threading.Thread(target=self.work, args=(owner, job_id, body), daemon=True)
            self.worker.start()
            return self.public(self.row(owner, job_id)), True

    def state(self, job_id: str, state: str):
        with closing(self.db()) as db, db:
            db.execute("UPDATE jobs SET state=? WHERE id=?", (state, job_id))

    def run_folder(self, owner: str, job_id: str) -> Path | None:
        folder = self.folder(owner, job_id)
        runs = list(folder.glob("*/manifest.json"))
        if len(runs) != 1:
            return None
        path = runs[0]
        if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
            raise APIError(404, "not_found")
        return path.parent

    def request_cancel(self, owner: str, job_id: str) -> dict:
        row = self.row(owner, job_id)
        if row["state"] in ("queued", "running"):
            with closing(self.db()) as db, db:
                db.execute("UPDATE jobs SET cancel=1 WHERE owner=? AND id=?", (owner, job_id))
        return self.public(self.row(owner, job_id))

    def cancel_workflow(self, folder: Path):
        # Use the existing authoritative cancellation flag; no lock stealing.
        database = folder / "workflow.sqlite"
        if database.is_file() and not database.is_symlink():
            from blackgrid.workflow.store import OperationStore
            store = OperationStore(database)
            try:
                rows = store.conn.execute("SELECT run_id FROM runs").fetchall()
                for row in rows:
                    store.request_cancel(row[0])
            finally:
                store.close()

    def work(self, owner: str, job_id: str, body: Submission):
        process = None
        try:
            folder = self.folder(owner, job_id)
            if hashlib.sha256(self.settings.config.read_bytes()).hexdigest() != self.config_sha256:
                raise ValueError("configuration changed")
            if self.row(owner, job_id)["cancel"]:
                self.state(job_id, "cancelled")
                return
            self.state(job_id, "running")
            argv = [sys.executable, "-m", "blackgrid", "run", str(self.settings.config.resolve()),
                    "--mode", "mock", "--family", "community", "--condition", body.condition,
                    "--data-root", str(self.settings.data_root.resolve()), "--runs-dir", str(folder.resolve()),
                    "--cache-dir", str((folder / "cache").resolve()), "--no-cache"]
            if body.question is not None:
                argv += ["--question", body.question]
            env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if k in os.environ}
            env.update(PYTHONPATH=str(ROOT / "src"), PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
            process = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self.lock:
                self.process = process
            deadline = time.monotonic() + 930
            while process.poll() is None:
                if self.row(owner, job_id)["cancel"]:
                    self.cancel_workflow(folder)
                if time.monotonic() > deadline:
                    self.state(job_id, "timed_out")
                    return
                time.sleep(.2)
            run = self.run_folder(owner, job_id)
            status = json.loads((run / "manifest.json").read_bytes()).get("status") if run else None
            terminal = {"completed": "completed", "cancelled": "cancelled", "abstained": "abstained"}
            self.state(job_id, "interrupted" if self.stopping else terminal.get(status, "failed"))
        except Exception:
            self.state(job_id, "failed")
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=3)
            with self.lock:
                self.process = None

    def results(self, owner: str, job_id: str) -> dict:
        row = self.row(owner, job_id)
        if row["state"] != "completed":
            raise APIError(409, "results_unavailable")
        run = self.run_folder(owner, job_id)
        if run is None:
            raise APIError(409, "results_unavailable")
        from blackgrid.analysis.parity import fingerprint
        # Never expose raw records, paths, prompts, trace bodies or node rankings.
        for name in ("investigation.json", "experiment_report.json", "sensitivity.json", "graph_record.json"):
            path = run / name
            if path.is_symlink() or (path.exists() and path.stat().st_size > 8 * 1024**2):
                raise APIError(409, "results_unavailable")
        result = fingerprint(run)
        if result["status"] != "completed":
            raise APIError(409, "results_unavailable")
        allowed = ("status", "verdict", "flags", "observed_q", "null_mean", "p_value", "exceedances",
                   "sensitivity_agreement", "llm_calls", "tokens_in", "tokens_out", "actual_usd")
        return {"job_id": job_id, "claim_type": "descriptive", "scope": "configured observed graph only",
                "summary": {key: result[key] for key in allowed}}

    def close(self):
        with self.lock:
            self.stopping = True
            worker = self.worker
        if worker:
            worker.join(self.settings.shutdown_grace_seconds)
            if worker.is_alive():
                with self.lock:
                    if self.process and self.process.poll() is None:
                        self.process.terminate()
                worker.join(5)
                if worker.is_alive():
                    with self.lock:
                        if self.process and self.process.poll() is None:
                            self.process.kill()
                    worker.join(5)
        self._lease.close()
