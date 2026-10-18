"""Durable operation and budget store (SQLite). See protocols/sprint02_workflow.md §3-§6.

Every paid or tool operation gets a row *before* its side effect, and its state moves
prepared -> dispatched -> succeeded | failed_known | billing_unknown inside transactions. Budget
totals are always summed from these rows, so a restart can never reset them. One active worker
per run is enforced with a lock row. This file is a local database, not a sandbox.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCHEMA_VERSION = 1
CURRENT_SPRINT = "sprint2"
OPEN_STATES = ("prepared", "dispatched")  # reservation still held, outcome not known
DONE_STATES = ("succeeded", "failed_known", "billing_unknown")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, sprint TEXT NOT NULL, created_utc TEXT NOT NULL, run_dir TEXT NOT NULL,
    status TEXT NOT NULL, status_reason TEXT, stage TEXT, pause_json TEXT,
    lock_owner TEXT, lock_pid INTEGER, heartbeat_utc TEXT,
    authorization_json TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
    revisions INTEGER NOT NULL DEFAULT 0, halted TEXT, parent_run TEXT, identity_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS operations (
    op_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, seq INTEGER NOT NULL, kind TEXT NOT NULL, name TEXT NOT NULL,
    call_index INTEGER NOT NULL, attempt INTEGER NOT NULL, input_sha256 TEXT NOT NULL, state TEXT NOT NULL,
    category TEXT, error TEXT, reserved_usd REAL NOT NULL DEFAULT 0, reserved_tokens INTEGER NOT NULL DEFAULT 0,
    prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0,
    actual_usd REAL NOT NULL DEFAULT 0, receipt_path TEXT, receipt_sha256 TEXT, records_json TEXT,
    created_utc TEXT NOT NULL, updated_utc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS budget_events (
    run_id TEXT NOT NULL, seq INTEGER NOT NULL, event_json TEXT NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS prior_spend (source TEXT PRIMARY KEY, sprint TEXT NOT NULL, usd REAL NOT NULL);
"""


class RunLocked(RuntimeError):
    """Another worker holds this run."""


class StoreError(RuntimeError):
    """The store or a run record is missing or inconsistent."""


def pid_alive(pid: int) -> bool:
    """Whether a process with this pid is running on this host. Unknown counts as alive (conservative)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists; otherwise it is gone
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)  # POSIX: signal 0 only checks existence (never used on Windows, where it kills)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Operation:
    op_id: str
    run_id: str
    kind: str
    name: str
    call_index: int
    attempt: int
    input_sha256: str
    state: str
    category: str | None
    error: str | None
    reserved_usd: float
    reserved_tokens: int
    prompt_tokens: int
    completion_tokens: int
    actual_usd: float
    receipt_path: str | None
    receipt_sha256: str | None
    records: list | None


class OperationStore:
    def __init__(self, path: Path | str) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        found = self.conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        if found is None:
            self.conn.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        elif int(found["value"]) != SCHEMA_VERSION:
            raise StoreError(f"operation store schema {found['value']} is not supported (expected {SCHEMA_VERSION})")

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise

    # --- prior spend (Sprint 1 imported once) -----------------------------------------------------

    def import_prior_spend(self, source: str, sprint: str, usd: float) -> None:
        with self.tx() as c:
            c.execute("INSERT OR IGNORE INTO prior_spend VALUES (?, ?, ?)", (source, sprint, usd))

    # --- runs ---------------------------------------------------------------------------------------

    def create_run(self, run_id: str, run_dir: Path, identity: dict, parent_run: str | None = None) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO runs (run_id, sprint, created_utc, run_dir, status, stage, identity_json, "
                      "parent_run) VALUES (?, ?, ?, ?, 'running', 'created', ?, ?)",
                      (run_id, CURRENT_SPRINT, now(), str(run_dir), json.dumps(identity, sort_keys=True),
                       parent_run))

    def run(self, run_id: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise StoreError(f"unknown run {run_id!r}")
        return row

    def runs(self) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM runs ORDER BY created_utc DESC").fetchall()

    def set_status(self, run_id: str, status: str, reason: str | None = None, stage: str | None = None,
                   pause: dict | None = None) -> None:
        with self.tx() as c:
            c.execute("UPDATE runs SET status=?, status_reason=?, stage=COALESCE(?, stage), pause_json=? "
                      "WHERE run_id=?", (status, reason, stage, json.dumps(pause) if pause else None, run_id))

    def set_stage(self, run_id: str, stage: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE runs SET stage=?, heartbeat_utc=? WHERE run_id=?", (stage, now(), run_id))

    def request_cancel(self, run_id: str) -> None:
        self.run(run_id)
        with self.tx() as c:
            c.execute("UPDATE runs SET cancel_requested=1 WHERE run_id=?", (run_id,))

    def cancel_requested(self, run_id: str) -> bool:
        return bool(self.run(run_id)["cancel_requested"])

    def set_authorization(self, run_id: str, scope: dict | None) -> None:
        with self.tx() as c:
            c.execute("UPDATE runs SET authorization_json=? WHERE run_id=?",
                      (json.dumps(scope, sort_keys=True) if scope else None, run_id))

    def authorization(self, run_id: str) -> dict | None:
        raw = self.run(run_id)["authorization_json"]
        return json.loads(raw) if raw else None

    def set_halted(self, run_id: str, reason: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE runs SET halted=? WHERE run_id=?", (reason, run_id))

    def set_revisions(self, run_id: str, revisions: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE runs SET revisions=? WHERE run_id=?", (revisions, run_id))

    # --- single-worker lock ---------------------------------------------------------------------------

    def acquire(self, run_id: str, *, force: bool = False) -> str:
        """Take the run's single-worker lease (Sprint 4 R1).

        Elapsed time alone never proves a worker is dead: heartbeats pause during a long tool call.
        A held lease is taken over only when its owner process has exited (checked on this host, so
        the store must not be shared across machines); a live but stalled owner needs a deliberate
        `force`. A reused pid looks alive, which errs towards refusing. A displaced owner is fenced:
        its next heartbeat or publication check raises RunLocked, so it cannot adopt a late result.
        """
        owner = uuid.uuid4().hex
        with self.tx() as c:
            row = c.execute("SELECT lock_owner, lock_pid, heartbeat_utc FROM runs WHERE run_id=?",
                            (run_id,)).fetchone()
            if row is None:
                raise StoreError(f"unknown run {run_id!r}")
            if row["lock_owner"] and not force:
                if row["lock_pid"] is None or pid_alive(row["lock_pid"]):
                    beat = datetime.fromisoformat(row["heartbeat_utc"]) if row["heartbeat_utc"] else None
                    age = f"last heartbeat {(datetime.now(UTC) - beat).total_seconds():.0f} s ago" if beat else                         "no heartbeat"
                    raise RunLocked(f"run {run_id} is held by another worker that is still running (pid "
                                    f"{row['lock_pid']}, {age}); a long tool call does not release it. Use "
                                    "--force-unlock only if that process has really stopped")
            c.execute("UPDATE runs SET lock_owner=?, lock_pid=?, heartbeat_utc=? WHERE run_id=?",
                      (owner, os.getpid(), now(), run_id))
        return owner

    def owns(self, run_id: str, owner: str) -> bool:
        row = self.conn.execute("SELECT lock_owner FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return row is not None and row["lock_owner"] == owner

    def heartbeat(self, run_id: str, owner: str) -> None:
        with self.tx() as c:
            row = c.execute("SELECT lock_owner FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if row is None or row["lock_owner"] != owner:
                raise RunLocked(f"run {run_id} lock was taken over by another worker")
            c.execute("UPDATE runs SET heartbeat_utc=? WHERE run_id=?", (now(), run_id))

    def release(self, run_id: str, owner: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE runs SET lock_owner=NULL, lock_pid=NULL WHERE run_id=? AND lock_owner=?",
                      (run_id, owner))

    # --- operations ----------------------------------------------------------------------------------

    def _op(self, row: sqlite3.Row | None) -> Operation | None:
        if row is None:
            return None
        return Operation(op_id=row["op_id"], run_id=row["run_id"], kind=row["kind"], name=row["name"],
                         call_index=row["call_index"], attempt=row["attempt"], input_sha256=row["input_sha256"],
                         state=row["state"], category=row["category"], error=row["error"],
                         reserved_usd=row["reserved_usd"], reserved_tokens=row["reserved_tokens"],
                         prompt_tokens=row["prompt_tokens"], completion_tokens=row["completion_tokens"],
                         actual_usd=row["actual_usd"], receipt_path=row["receipt_path"],
                         receipt_sha256=row["receipt_sha256"],
                         records=json.loads(row["records_json"]) if row["records_json"] else None)

    def get(self, op_id: str) -> Operation | None:
        return self._op(self.conn.execute("SELECT * FROM operations WHERE op_id=?", (op_id,)).fetchone())

    def operations(self, run_id: str, kind: str | None = None) -> list[Operation]:
        sql, args = "SELECT * FROM operations WHERE run_id=?", [run_id]
        if kind:
            sql, args = sql + " AND kind=?", args + [kind]
        return [self._op(r) for r in self.conn.execute(sql + " ORDER BY seq", args).fetchall()]

    def prepare(self, op_id: str, run_id: str, kind: str, name: str, call_index: int, attempt: int,
                input_sha256: str, reserved_usd: float = 0.0, reserved_tokens: int = 0) -> None:
        with self.tx() as c:
            seq = c.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM operations WHERE run_id=?", (run_id,)).fetchone()[0]
            c.execute("INSERT INTO operations (op_id, run_id, seq, kind, name, call_index, attempt, input_sha256, "
                      "state, reserved_usd, reserved_tokens, created_utc, updated_utc) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'prepared', ?, ?, ?, ?)",
                      (op_id, run_id, seq, kind, name, call_index, attempt, input_sha256, reserved_usd,
                       reserved_tokens, now(), now()))

    def transition(self, op_id: str, state: str, **fields: object) -> None:
        allowed = {"category", "error", "prompt_tokens", "completion_tokens", "actual_usd", "receipt_path",
                   "receipt_sha256", "records_json"}
        assert set(fields) <= allowed, set(fields) - allowed
        sets = ", ".join(f"{k}=?" for k in fields)
        with self.tx() as c:
            c.execute(f"UPDATE operations SET state=?, updated_utc=?{', ' + sets if sets else ''} WHERE op_id=?",
                      (state, now(), *fields.values(), op_id))

    # --- budget totals (always from durable rows) -------------------------------------------------------

    def run_totals(self, run_id: str) -> dict:
        """Calls, tokens, and money for one run. Open operations count at their full reservation."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS calls, "
            "COALESCE(SUM(CASE WHEN state IN ('prepared','dispatched') THEN reserved_tokens ELSE "
            "prompt_tokens + completion_tokens END), 0) AS tokens, "
            "COALESCE(SUM(CASE WHEN state IN ('prepared','dispatched') THEN reserved_usd ELSE actual_usd END), 0) "
            "AS usd, COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, "
            "COALESCE(SUM(completion_tokens), 0) AS completion_tokens "
            "FROM operations WHERE run_id=? AND kind='llm'", (run_id,)).fetchone()
        run = self.run(run_id)
        return {"calls": row["calls"], "tokens": row["tokens"], "usd": row["usd"],
                "prompt_tokens": row["prompt_tokens"], "completion_tokens": row["completion_tokens"],
                "revisions": run["revisions"], "halted": run["halted"]}

    def spend_elsewhere(self, run_id: str) -> tuple[float, float]:
        """(project-wide spend, current-sprint spend) by every other run, plus imported prior spend."""
        total = sprint = 0.0
        for row in self.conn.execute(
                "SELECT r.sprint AS sprint, SUM(CASE WHEN o.state IN ('prepared','dispatched') THEN o.reserved_usd "
                "ELSE o.actual_usd END) AS usd FROM operations o JOIN runs r ON r.run_id=o.run_id "
                "WHERE o.kind='llm' AND o.run_id<>? GROUP BY r.sprint", (run_id,)):
            total += row["usd"] or 0.0
            sprint += (row["usd"] or 0.0) if row["sprint"] == CURRENT_SPRINT else 0.0
        for row in self.conn.execute("SELECT sprint, usd FROM prior_spend"):
            total += row["usd"]
            sprint += row["usd"] if row["sprint"] == CURRENT_SPRINT else 0.0
        return total, sprint

    def append_event(self, run_id: str, event: dict) -> None:
        with self.tx() as c:
            seq = c.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM budget_events WHERE run_id=?",
                            (run_id,)).fetchone()[0]
            c.execute("INSERT INTO budget_events VALUES (?, ?, ?)", (run_id, seq, json.dumps(event, sort_keys=True)))

    def events(self, run_id: str) -> list[dict]:
        return [json.loads(r["event_json"]) for r in
                self.conn.execute("SELECT event_json FROM budget_events WHERE run_id=? ORDER BY seq", (run_id,))]
