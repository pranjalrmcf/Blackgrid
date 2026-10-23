"""Single-host API admission and ownership around the existing trusted CLI."""
from __future__ import annotations

import hashlib
import json
import os
import random
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

from pydantic import Field, model_validator

from blackgrid.contracts import Contract, RunConfig
from blackgrid.operations.live import Broker, load_policy
from blackgrid.operations.settings import ROOT, Settings
from blackgrid.operations.api_tools import CATALOG, expanded_results, read_artifact
from blackgrid.workflow.evidence import ToolEvidence
from blackgrid.operations import telemetry
from blackgrid.operations import tool_cache

TOOL_ANALYSES = {name: description for name, (_, description) in CATALOG.items()}


class Submission(Contract):
    mode: Literal["mock", "live"] = "mock"
    scope: Literal["first_window"] = "first_window"
    condition: Literal["validated", "tool_only"] = "validated"
    question: str | None = Field(default=None, min_length=1, max_length=500)
    allow_paid: bool = Field(default=False, strict=True, exclude=True)

    @model_validator(mode="after")
    def authorization(self):
        if (self.mode == "live") != self.allow_paid:
            raise ValueError("live requests require explicit paid authorization")
        return self


class APIError(Exception):
    def __init__(self, status: int, code: str):
        self.status, self.code = status, code


class Jobs:
    # One scientific workflow at a time; at most eight accepted waiting jobs.
    QUEUE_CAPACITY = 8
    MAX_ATTEMPTS = 3
    EXECUTION_SECONDS = 930

    def __init__(self, settings: Settings):
        self.settings = settings
        self.live_policy = load_policy()
        self.config_sha256 = hashlib.sha256(settings.config.read_bytes()).hexdigest()
        self.cache_identity = tool_cache.implementation_identity(ROOT) if settings.api_tool_cache else None
        self.root = settings.runs_dir / "api"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink():
            raise ValueError("unsafe API state")
        self.lock = threading.RLock()
        self.stopping = False
        self.scheduler_failed = False
        self.wake = threading.Event()
        self.worker: threading.Thread | None = None
        self.dispatching = False
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
            columns = {r[1] for r in db.execute("PRAGMA table_info(jobs)")}
            for name, definition in (("mode", "TEXT NOT NULL DEFAULT 'mock'"),
                    ("reserved_usd", "REAL NOT NULL DEFAULT 0"), ("charged_usd", "REAL NOT NULL DEFAULT 0"),
                    ("billing", "TEXT NOT NULL DEFAULT 'none'"), ("error_code", "TEXT"),
                    ("submission", "TEXT"), ("config_hash", "TEXT"), ("started", "TEXT"),
                    ("finished", "TEXT"), ("attempts", "INTEGER NOT NULL DEFAULT 0"),
                    ("not_before", "REAL NOT NULL DEFAULT 0"), ("deadline", "REAL"), ("result_ref", "TEXT"),
                    ("routing", "TEXT NOT NULL DEFAULT 'community'"), ("evidence_hash", "TEXT")):
                if name not in columns:
                    db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
            db.execute("CREATE TABLE IF NOT EXISTS live_policy (id INTEGER PRIMARY KEY, fingerprint TEXT NOT NULL)")
            if self.live_policy:
                self.live_policy.key()  # validate presence without contacting the provider
                self.policy_fingerprint = self.live_fingerprint()
                previous = db.execute("SELECT fingerprint FROM live_policy WHERE id=1").fetchone()
                if previous and previous[0] != self.policy_fingerprint:
                    raise ValueError("retained live authorization changed; review ledger before migration")
                db.execute("INSERT OR IGNORE INTO live_policy VALUES(1,?)", (self.policy_fingerprint,))
            # Legacy jobs have no recoverable request envelope. Never invent one.
            db.execute("""UPDATE jobs SET state='interrupted',error_code='recovery_review_required',
                finished=? WHERE state IN ('queued','running') AND (submission IS NULL OR mode='live' AND state='running')""",
                (datetime.now(UTC).isoformat(),))
            db.execute("UPDATE jobs SET billing='held' WHERE mode='live' AND state='interrupted' AND billing='reserved'")
            # Only mock work may resume automatically. The worker takes an exclusive
            # execution lock before force-unlocking the existing scientific checkpoint.
            db.execute("""UPDATE jobs SET state='queued',finished=NULL,error_code='worker_interrupted'
                WHERE state IN ('running','interrupted') AND mode='mock' AND submission IS NOT NULL""")
        self.kick()

    def live_fingerprint(self):
        return hashlib.sha256((self.live_policy.model_dump_json() +
            hashlib.sha256(self.live_policy.config.read_bytes()).hexdigest()).encode()).hexdigest()

    def live_usage(self, db, exclude=None):
        spent = db.execute("""SELECT COALESCE(SUM(CASE WHEN billing IN ('reserved','held')
            THEN MAX(reserved_usd,charged_usd) ELSE charged_usd END),0) FROM jobs WHERE mode='live' AND id<>?""",
                           (exclude or "",)).fetchone()[0]
        return self.live_policy.prior_spend_usd + spent

    def live_preflight(self, owner, db):
        policy = self.live_policy
        if not policy or owner not in policy.subjects:
            raise APIError(403, "live_not_authorized")
        if sys.platform != "linux":
            raise APIError(503, "live_requires_linux_container")
        if self.live_fingerprint() != self.policy_fingerprint:
            raise APIError(503, "live_configuration_changed")
        policy.key()
        other = self.live_usage(db)
        # Reserve a whole existing per-investigation cap, not merely an optimistic estimate.
        if other + policy.max_per_job_usd > policy.ceiling_project_usd + 1e-12:
            raise APIError(403, "live_budget_exhausted")
        policy.config_for(RunConfig.model_validate_json(self.settings.config.read_bytes()), other)

    def db(self):
        db = sqlite3.connect(self.root / "jobs.sqlite", timeout=5)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def row(self, owner: str, job_id: str) -> dict:
        with closing(self.db()) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM jobs WHERE owner=? AND id=?", (owner, job_id)).fetchone()
        if row is None:
            raise APIError(404, "not_found")
        return dict(row)

    def available(self):
        if self.stopping or self.scheduler_failed:
            return False
        try:
            with closing(self.db()) as db:
                db.execute("SELECT id FROM jobs LIMIT 1").fetchone()
        except sqlite3.Error:
            self.scheduler_failed = True
            return False
        return True

    def public(self, row: dict) -> dict:
        result = {"job_id": row["id"], "state": row["state"], "created_utc": row["created"],
                "cancel_requested": bool(row["cancel"]), "mode": row["mode"], "error_code": row["error_code"]}
        result.update(started_utc=row["started"], completed_utc=row["finished"], attempts=row["attempts"],
                      result_ref=row["result_ref"], recovery_required=row["state"] in ("interrupted", "paused"))
        result["progress"] = {"stage": row["state"], "llm_calls": 0, "actual_usd": row["charged_usd"],
                              "reserved_usd": row["reserved_usd"] if row["billing"] in ("reserved", "held") else 0,
                              "current_tool": None, "analysis": None, "tools": []}
        folder = self.folder(row["owner"], row["id"])
        database = folder / "workflow.sqlite"
        if database.is_file() and not database.is_symlink():
            try:
                with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=.2)) as db:
                    stage = db.execute("SELECT stage FROM runs LIMIT 1").fetchone()
                    totals = db.execute("SELECT COUNT(1),COALESCE(SUM(actual_usd),0) FROM operations WHERE kind='llm'").fetchone()
                    tools = db.execute("""SELECT seq,name,state,updated_utc,records_json FROM operations
                        WHERE kind='tool' ORDER BY seq DESC LIMIT 100""").fetchall()
                result["progress"].update(stage=stage[0] if stage else row["state"], llm_calls=totals[0], actual_usd=totals[1])
                for seq, name, state, updated, records in reversed(tools):
                    if name in TOOL_ANALYSES and state in ("prepared", "dispatched", "succeeded", "failed_known"):
                        try:
                            saved = json.loads(records or '[]') if len(records or '') <= 262144 else []
                            cached = any(isinstance(r,dict) and r.get('tool') == name and r.get('cached') is True for r in saved)
                        except (ValueError,TypeError):
                            cached = False
                        result["progress"]["tools"].append({"sequence": seq, "tool": name, "state": state,
                            "analysis": TOOL_ANALYSES[name], "updated_utc": updated,"cached":cached})
                        if state in ("prepared", "dispatched") and row["state"] == "running":
                            result["progress"].update(current_tool=name, analysis=TOOL_ANALYSES[name])
            except sqlite3.Error:
                pass
        return result

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
                db.execute("BEGIN IMMEDIATE")
                found = db.execute("SELECT id,digest FROM jobs WHERE owner=? AND idem=?", (owner, idem)).fetchone()
                if found:
                    if found[1] != digest:
                        raise APIError(409, "idempotency_conflict")
                    return self.public(self.row(owner, found[0])), False
                if self.stopping or self.scheduler_failed:
                    raise APIError(503, "worker_unavailable")
                if db.execute("SELECT COUNT(*) FROM jobs WHERE state='queued'").fetchone()[0] >= self.QUEUE_CAPACITY:
                    raise APIError(503, "queue_full")
                if hashlib.sha256(self.settings.config.read_bytes()).hexdigest() != self.config_sha256:
                    raise APIError(503, "configuration_changed")
                if db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] >= 5000:
                    raise APIError(503, "job_capacity_reached")
                if body.mode == "live":
                    self.live_preflight(owner, db)
                job_id = uuid.uuid4().hex
                folder = self.folder(owner, job_id)
                folder.parent.mkdir(exist_ok=True, mode=0o700)
                folder.mkdir(mode=0o700)
                payload = body.model_dump() | {"allow_paid": body.allow_paid}
                evidence = ToolEvidence.capture(self.settings.evidence_root).model_dump_json()
                (folder / "tool-evidence.json").write_text(evidence, encoding="utf-8")
                db.execute("""INSERT INTO jobs (id,owner,idem,digest,state,created,mode,reserved_usd,billing,
                    submission,config_hash,routing,evidence_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                           (job_id, owner, idem, digest, "queued", datetime.now(UTC).isoformat(), body.mode,
                            self.live_policy.max_per_job_usd if body.mode == "live" else 0,
                            "reserved" if body.mode == "live" else "none", json.dumps(payload), self.config_sha256,
                            "auto", hashlib.sha256(evidence.encode()).hexdigest()))
                db.commit()
            with telemetry.span("job_scheduling", context=telemetry.job_context(folder, owner, job_id)):
                pass
            self.kick()
            return self.public(self.row(owner, job_id)), True

    def kick(self):
        with self.lock:
            self.wake.set()
            if self.stopping or self.scheduler_failed or self.dispatching:
                return
            with closing(self.db()) as db:
                if not db.execute("SELECT 1 FROM jobs WHERE state='queued' LIMIT 1").fetchone():
                    return
            self.worker = threading.Thread(target=self.dispatch, daemon=True)
            self.dispatching = True
            self.worker.start()

    def dispatch(self):
        try:
            while True:
                with self.lock:
                    if self.stopping or self.scheduler_failed:
                        self.dispatching = False
                        return
                    with closing(self.db()) as db, db:
                        db.row_factory = sqlite3.Row
                        db.execute("BEGIN IMMEDIATE")
                        row = db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY not_before,created,id LIMIT 1").fetchone()
                        if row is None:
                            # Clear under the same lock used by submit/kick: no lost wakeup.
                            self.dispatching = False
                            return
                        row = dict(row)
                        exhausted = row["attempts"] >= self.MAX_ATTEMPTS
                        expired = row["deadline"] and time.time() >= row["deadline"]
                        if exhausted or expired:
                            db.execute("UPDATE jobs SET state=?,finished=?,error_code='recovery_limit_reached' WHERE id=?",
                                ("timed_out" if expired else "failed", datetime.now(UTC).isoformat(), row["id"]))
                            continue
                        delay = row["not_before"] - time.time()
                        if delay <= 0:
                            now = datetime.now(UTC).isoformat()
                            db.execute("""UPDATE jobs SET state='running',started=COALESCE(started,?),
                                deadline=COALESCE(deadline,?),attempts=attempts+1 WHERE id=? AND state='queued'""",
                                (now, time.time() + self.EXECUTION_SECONDS, row["id"]))
                    self.wake.clear()
                if delay > 0:
                    self.wake.wait(min(delay, 1))
                    continue
                try:
                    body = Submission.model_validate_json(row["submission"])
                    if (row["config_hash"] != self.config_sha256 or body.mode != row["mode"]
                            or hashlib.sha256(body.model_dump_json().encode()).hexdigest() != row["digest"]):
                        raise ValueError("configuration changed")
                except (ValueError, TypeError):
                    if row["mode"] == "live":
                        self.settle_live(row["owner"], row["id"], False, True,
                                         final_state="failed", error="invalid_recovery_envelope")
                    else:
                        self.state(row["id"], "failed", error="invalid_recovery_envelope")
                    continue
                context = telemetry.job_context(self.folder(row["owner"], row["id"]), row["owner"], row["id"])
                with telemetry.span("agent_execution", context=context):
                    self.work(row["owner"], row["id"], body)
                # Test doubles and unexpected wrapper exits cannot strand a running job.
                current = self.row(row["owner"], row["id"])
                if current["state"] == "running":
                    self.state(row["id"], "interrupted", error="worker_interrupted")
        except Exception:
            # Database failures stop admission; persisted claims are recovered on restart.
            with self.lock:
                self.scheduler_failed = True
                self.dispatching = False

    def state(self, job_id: str, state: str, *, error=None, result=None):
        with closing(self.db()) as db, db:
            db.execute("UPDATE jobs SET state=?,error_code=?,finished=?,result_ref=? WHERE id=?",
                (state, error, None if state in ("running", "queued") else datetime.now(UTC).isoformat(), result, job_id))

    def run_folder(self, owner: str, job_id: str) -> Path | None:
        folder = self.folder(owner, job_id)
        runs = list(folder.glob("*/manifest.json"))
        if len(runs) != 1:
            return None
        path = runs[0]
        if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
            raise APIError(404, "not_found")
        return path.parent

    def checkpoint_run(self, owner: str, job_id: str) -> Path | None:
        folder = self.folder(owner, job_id)
        database = folder / "workflow.sqlite"
        if not database.exists():
            return None
        if database.is_symlink():
            raise ValueError("unsafe checkpoint")
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            rows = db.execute("SELECT run_id,run_dir FROM runs").fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise ValueError("ambiguous checkpoint")
        run_id, saved = rows[0]
        path = Path(saved)
        if (path.name != run_id or path.parent.resolve() != folder.resolve() or path.is_symlink()
                or not path.is_dir() or not all(c.isalnum() or c in "-_" for c in run_id)):
            raise ValueError("unsafe checkpoint")
        for name in ("config.json", "run_source.json"):
            source = path / name
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 1024**2:
                raise ValueError("invalid checkpoint")
        return path

    def request_cancel(self, owner: str, job_id: str) -> dict:
        with self.lock, closing(self.db()) as db, db:
            self.row(owner, job_id)
            db.execute("UPDATE jobs SET cancel=1 WHERE owner=? AND id=? AND state IN ('queued','running')", (owner, job_id))
            db.execute("""UPDATE jobs SET state='cancelled',finished=?,billing=CASE WHEN mode='live'
                THEN 'settled' ELSE billing END WHERE owner=? AND id=? AND state='queued'""",
                (datetime.now(UTC).isoformat(), owner, job_id))
            self.wake.set()
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
        broker = None
        safe_zero = False
        outcome, error, result = "failed", "execution_failed", None
        try:
            folder = self.folder(owner, job_id)
            job = self.row(owner, job_id)
            routing = job["routing"]
            if routing not in ("community", "auto"):
                raise ValueError("invalid saved routing policy")
            evidence_path = folder / "tool-evidence.json"
            if routing == "auto" and (evidence_path.is_symlink() or not evidence_path.is_file()
                    or hashlib.sha256(evidence_path.read_bytes()).hexdigest() != job["evidence_hash"]):
                outcome, error = "failed", "tool_evidence_binding_changed"
                return
            if hashlib.sha256(self.settings.config.read_bytes()).hexdigest() != self.config_sha256:
                raise ValueError("configuration changed")
            if self.row(owner, job_id)["cancel"]:
                outcome, error = "cancelled", None
                safe_zero = True
                return
            config_path = self.settings.config.resolve()
            if body.mode == "live":
                if not self.live_policy or self.live_fingerprint() != self.policy_fingerprint:
                    outcome, error, safe_zero = "failed", "live_configuration_changed", True
                    return
                with closing(self.db()) as db:
                    other = self.live_usage(db, exclude=job_id)
                live_config = self.live_policy.config_for(RunConfig.model_validate_json(config_path.read_bytes()), other)
                config_path = folder / "api-live-config.json"
                config_path.write_text(live_config.model_dump_json(indent=2))
                from blackgrid.workflow.api import open_services
                services = open_services(folder)
                try:
                    services.store.import_prior_spend("api:retained-project-accounting", "sprint2", other)
                finally:
                    services.close()
            cache = (tool_cache.directory(self.root/'tool-cache',owner,body.mode,self.config_sha256,self.cache_identity)
                     if self.settings.api_tool_cache else None)
            cache_args = ['--cache-dir',str(cache.resolve())] if cache else ['--no-cache']
            argv = [sys.executable, "-m", "blackgrid.operations.worker", "run", str(config_path),
                    "--mode", body.mode, "--family", routing, "--condition", body.condition,
                    "--data-root", str(self.settings.data_root.resolve()), "--runs-dir", str(folder.resolve()),
                    *cache_args]
            if body.question is not None:
                argv += ["--question", body.question]
            # Recovery uses the existing checkpoint and receipt verification. Never
            # create a second run over partially written scientific artifacts.
            if self.row(owner, job_id)["attempts"] > 1:
                run = self.checkpoint_run(owner, job_id)
                if run:
                    argv = [sys.executable, "-m", "blackgrid.operations.worker", "resume", run.name,
                            "--runs-dir", str(folder.resolve()), *cache_args, "--force-unlock"]
                elif any(p.name not in ("execution.lock", "cache", "tool-evidence.json", "telemetry.jsonl") for p in folder.iterdir()):
                    outcome, error = "failed", "partial_artifacts_require_review"
                    return
            env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if k in os.environ}
            env.update(PYTHONPATH=str(ROOT / "src"), PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
            env.update(telemetry.worker_environment())
            if self.settings.benchmark_mock_profile != "none":
                env["BLACKGRID_BENCHMARK_MOCK_PROFILE"] = self.settings.benchmark_mock_profile
                env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
            env.update(BLACKGRID_JOB_LOCK_FILE=str(folder / "execution.lock"),
                       BLACKGRID_WORKER_PARENT=str(os.getpid()))
            if routing == "auto":
                env["BLACKGRID_TOOL_EVIDENCE_FILE"] = str(evidence_path)
            extra = {}
            if body.mode == "live":
                broker = Broker(self.live_policy)
                env.update(BLACKGRID_PROVIDER_BROKER_FD=str(broker.child.fileno()),
                           OPEN_ROUTER_API_KEY="private-broker-managed")
                argv += ["--allow-paid", "--env-file", str(folder / "no-external-env-file")]
                extra["pass_fds"] = (broker.child.fileno(),)
            try:
                process = subprocess.Popen(argv, cwd=ROOT, env=env, close_fds=True, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **extra)
            except OSError:
                outcome, error = "failed", "worker_start_failed"
                return
            if broker:
                broker.start()
            with self.lock:
                self.process = process
            deadline = self.row(owner, job_id)["deadline"] or time.time() + self.EXECUTION_SECONDS
            logged = len(telemetry.read_spans(folder / "telemetry.jsonl"))
            while process.poll() is None:
                records = telemetry.read_spans(folder / "telemetry.jsonl")
                for record in records[logged:]:
                    telemetry.emit(record)
                logged = len(records)
                if self.row(owner, job_id)["cancel"]:
                    self.cancel_workflow(folder)
                if time.time() > deadline:
                    outcome, error = "timed_out", "execution_deadline_exceeded"
                    return
                time.sleep(.2)
            for record in telemetry.read_spans(folder / "telemetry.jsonl")[logged:]:
                telemetry.emit(record)
            run = self.run_folder(owner, job_id)
            status = json.loads((run / "manifest.json").read_bytes()).get("status") if run else None
            terminal = {"completed": "completed", "cancelled": "cancelled", "abstained": "abstained", "partial": "partial"}
            outcome = terminal.get(status, "interrupted" if self.stopping else "paused" if process.returncode == 3 else "failed")
            error = None if outcome in terminal.values() else (
                "worker_lock_busy" if process.returncode == 75 else
                "worker_crashed" if process.returncode < 0 else
                "recovery_review_required" if outcome in ("paused", "interrupted") else "execution_failed")
            if outcome in ("partial", "abstained"):
                error = "analysis_incomplete" if outcome == "partial" else "analysis_abstained"
            if outcome == "completed":
                from blackgrid.analysis.parity import fingerprint
                if fingerprint(run)["status"] != "completed":
                    outcome, error = "failed", "incomplete_result_artifacts"
                    return
                result = f"/api/v1/jobs/{job_id}/results"
        except Exception:
            outcome, error = "failed", "execution_failed"
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=3)
            with self.lock:
                self.process = None
            if self.settings.api_tool_cache:
                try:
                    tool_cache.prune(self.root/'tool-cache')
                except (OSError,ValueError):
                    pass  # Disposable optimization data cannot replace a scientific/billing outcome.
            if broker:
                broker.close()
            if body.mode == "live":
                if outcome not in ("completed", "cancelled", "abstained") and broker and broker.failure_code:
                    error = broker.failure_code
                self.settle_live(owner, job_id, process is not None, safe_zero,
                                 final_state=outcome, error=error, result=result)
            else:
                attempt = self.row(owner, job_id)["attempts"]
                if (not self.stopping and outcome == "failed" and error in
                        ("worker_crashed", "worker_start_failed", "worker_lock_busy") and attempt < self.MAX_ATTEMPTS):
                    # Full jitter, capped exponential backoff. No terminal state is
                    # published while a safe local retry is still pending.
                    with closing(self.db()) as db, db:
                        db.execute("UPDATE jobs SET state='queued',finished=NULL,error_code=?,not_before=? WHERE id=?",
                            (error, time.time() + random.uniform(0, min(8, 2 ** attempt)), job_id))
                else:
                    self.state(job_id, outcome, error=error, result=result)

    def settle_live(self, owner, job_id, started, safe_zero, *, final_state=None, error=None, result=None):
        billing, charged = "held", 0.0
        database = self.folder(owner, job_id) / "workflow.sqlite"
        try:
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as source:
                rows = source.execute("SELECT state,actual_usd,reserved_usd FROM operations WHERE kind='llm'").fetchall()
            charged = sum(r[1] for r in rows)
            if all(r[0] in ("succeeded", "failed_known") for r in rows) and (final_state or self.row(owner, job_id)["state"]) not in ("interrupted", "timed_out"):
                billing, charged = "settled", sum(r[1] for r in rows)
        except (OSError, sqlite3.Error):
            if safe_zero or not started:
                billing = "settled"
        with closing(self.db()) as db, db:
            db.execute("UPDATE jobs SET billing=?,charged_usd=? WHERE id=?", (billing, charged, job_id))
            if final_state:
                # Terminal state, cost, result reference and sanitized failure become
                # visible in the same commit, after the child has stopped.
                db.execute("UPDATE jobs SET state=?,finished=?,error_code=?,result_ref=? WHERE id=?",
                    (final_state, datetime.now(UTC).isoformat(), error, result, job_id))
            elif self.row(owner, job_id)["state"] == "failed":
                db.execute("UPDATE jobs SET error_code='live_execution_failed' WHERE id=?", (job_id,))

    def results(self, owner: str, job_id: str) -> dict:
        row = self.row(owner, job_id)
        if row["state"] not in ("completed", "abstained", "partial"):
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
        allowed = ("status", "verdict", "flags", "observed_q", "null_mean", "p_value", "exceedances",
                   "sensitivity_agreement", "llm_calls", "tokens_in", "tokens_out", "actual_usd")
        try:
            result = fingerprint(run)
            if result["status"] != row["state"]:
                raise APIError(409, "results_unavailable")
            expanded = expanded_results(run, read_artifact(run, "investigation.json"))
            summary = {key: result[key] for key in allowed}
        except (ValueError, OSError, TypeError, KeyError):
            raise APIError(409, "results_unavailable") from None
        if expanded["family"] != "community":
            for key in ("observed_q", "null_mean", "p_value", "exceedances", "sensitivity_agreement"):
                summary.pop(key, None)
        return {"job_id": job_id, **expanded, "summary": summary}

    def close(self):
        with self.lock:
            self.stopping = True
            self.wake.set()
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
            if worker.is_alive():
                # Never permit a replacement scheduler while this one can still write.
                raise RuntimeError("worker shutdown incomplete; state lease retained")
        self._lease.close()
