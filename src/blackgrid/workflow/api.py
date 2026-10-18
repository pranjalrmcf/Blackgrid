"""Start, resume, cancel, deny, reconcile, and inspect workflow runs.

Durable files per runs directory (all git-ignored, all sensitive local artifacts):
    runs/workflow.sqlite     operations, budget events, run records, locks, authorizations
    runs/checkpoints.sqlite  LangGraph checkpoints (state only: no secrets, graphs, or raw records)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from blackgrid.agent.roles import PROMPT_VERSION, InvestigationInput, InvestigationResult
from blackgrid.contracts import BudgetLimits, ExecutionMode, RunStatus, canonical_sha256
from blackgrid.agent.critic import CRITIC_VERSION
from blackgrid.agent.providers import Provider
from blackgrid.workflow.engine import (
    WORKFLOW_VERSION,
    ResumeBlocked,
    Runtime,
    SimulatedCrash,
    build,
    build_result,
    expected_scope,
    validate_state,
    write_json,
)
from blackgrid.workflow.store import OperationStore, RunLocked

RESUMABLE = {"running", "paused"}


@dataclass
class Services:
    store: OperationStore
    saver: object  # a LangGraph checkpointer

    def close(self) -> None:
        self.store.close()
        conn = getattr(self.saver, "conn", None)
        if conn is not None:
            conn.close()


def open_services(runs_dir: Path | None) -> Services:
    """Durable SQLite services in `runs_dir`, or in-memory services when `runs_dir` is None."""
    if runs_dir is None:
        return Services(store=OperationStore(":memory:"), saver=InMemorySaver())
    runs_dir.mkdir(parents=True, exist_ok=True)
    store = OperationStore(runs_dir / "workflow.sqlite")
    saver = SqliteSaver(sqlite3.connect(runs_dir / "checkpoints.sqlite", check_same_thread=False))
    legacy = runs_dir / "spend_ledger.json"  # Sprint 1 live spend, imported once so it is never forgotten
    if legacy.is_file():
        store.import_prior_spend("sprint1:spend_ledger.json", "sprint1",
                                 float(json.loads(legacy.read_text(encoding="utf-8")).get("total_usd", 0.0)))
    return Services(store=store, saver=saver)


@dataclass
class Outcome:
    run_id: str
    run_dir: Path
    status: str
    reason: str | None
    pause: dict | None
    result: InvestigationResult | None = None
    ctx: object | None = None  # ToolContext of the finished run (in-process callers only)


def identity_of(inp: InvestigationInput, config_sha256: str, model: str, condition: str, mode: ExecutionMode,
                input_ref: dict) -> dict:
    return {"workflow_version": WORKFLOW_VERSION, "config_sha256": config_sha256,
            "spec_sha256": canonical_sha256(inp.spec), "projection_sha256": inp.record.projection_sha256,
            "model": model, "prompt_version": PROMPT_VERSION, "critic_version": CRITIC_VERSION,
            "condition": condition, "mode": mode.value, "input_ref": input_ref}


@dataclass
class RunSpec:
    """Everything needed to (re)build a Runtime; nothing here is checkpointed."""

    limits: BudgetLimits
    mode: ExecutionMode
    condition: str
    max_tokens: int
    model: str
    config_sha256: str
    provider_factory: Callable[[], Provider]
    loader: Callable[[dict], InvestigationInput]
    cache_dir: Path | None = None
    sensitivity_null_replicates: int | None = None
    on_finalize: Callable | None = None
    on_render: Callable | None = None
    deadline_s: float = 900.0


def _runtime(services: Services, run_id: str, run_dir: Path, spec: RunSpec, owner: str,
             faults: set[str] | None) -> Runtime:
    return Runtime(store=services.store, run_id=run_id, run_dir=run_dir, mode=spec.mode, condition=spec.condition,
                   limits=spec.limits, max_tokens=spec.max_tokens, provider_factory=spec.provider_factory,
                   loader=spec.loader, cache_dir=spec.cache_dir,
                   sensitivity_null_replicates=spec.sensitivity_null_replicates, owner=owner, faults=set(faults or ()),
                   deadline_s=spec.deadline_s, on_finalize=spec.on_finalize, on_render=spec.on_render)


def _mark_interrupted(services: Services, rt: Runtime) -> None:
    """An interrupted worker is no longer running: record a resumable pause, never a stale 'running' (R5).

    Any dispatched paid call keeps its operation state, so resume still applies reconciliation rules.
    """
    if not services.store.owns(rt.run_id, rt.owner):
        return  # displaced: the current owner decides the status
    reason = "interrupted: the worker process stopped; run `blackgrid resume` to continue"
    services.store.set_status(rt.run_id, "paused", reason, pause={"kind": "interrupted", "reason": reason})
    path = rt.run_dir / "workflow_status.json"
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"run_id": rt.run_id}
        write_json(path, current | {"status": "paused", "reason": reason,
                                    "pause": {"kind": "interrupted", "reason": reason},
                                    "updated_utc": datetime.now(UTC).isoformat()})
    except (OSError, ValueError):
        pass  # the store row above is authoritative


def _mark_internal_error(services: Services, rt: Runtime, exc: BaseException) -> None:
    """An unexpected error stopped the worker: record a resumable pause with the reason (D-075).

    The run is not 'running' any more, so the console stops polling it. Once the cause is fixed,
    `blackgrid resume` continues from the last checkpoint; paid-call states are unchanged, so
    reconciliation rules still apply.
    """
    if not services.store.owns(rt.run_id, rt.owner):
        return
    reason = f"internal_error: {type(exc).__name__}: {str(exc).splitlines()[0][:240] if str(exc) else ''}".rstrip(": ")
    pause = {"kind": "internal_error", "reason": reason + "; fix the cause, then run `blackgrid resume`"}
    services.store.set_status(rt.run_id, "paused", reason, pause=pause)
    path = rt.run_dir / "workflow_status.json"
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"run_id": rt.run_id}
        write_json(path, current | {"status": "paused", "reason": reason, "pause": pause,
                                    "updated_utc": datetime.now(UTC).isoformat()})
    except (OSError, ValueError):
        pass  # the store row above is authoritative


def _drive(services: Services, rt: Runtime, payload: object) -> Outcome:
    graph = build(rt).compile(checkpointer=services.saver)
    cfg = {"configurable": {"thread_id": rt.run_id}}
    try:
        values = graph.invoke(payload, cfg, durability="sync")
    except SimulatedCrash:
        raise  # a simulated process death: leave the lock and state exactly as a crash would
    except (KeyboardInterrupt, SystemExit):
        _mark_interrupted(services, rt)
        services.store.release(rt.run_id, rt.owner)
        raise
    except RunLocked:
        raise  # displaced: the current owner decides the status
    except BaseException as exc:
        _mark_internal_error(services, rt, exc)
        services.store.release(rt.run_id, rt.owner)
        raise
    services.store.release(rt.run_id, rt.owner)
    row = services.store.run(rt.run_id)
    if "__interrupt__" in values:
        pause = json.loads(row["pause_json"]) if row["pause_json"] else None
        result, ctx = build_result(rt, values)
        result = result.model_copy(update={"status": RunStatus.PAUSED, "failure_reason": row["status_reason"]})
        return Outcome(rt.run_id, rt.run_dir, "paused", row["status_reason"], pause, result, ctx)
    result, ctx = build_result(rt, values)
    return Outcome(rt.run_id, rt.run_dir, result.status.value, result.failure_reason, None, result, ctx)


def start(inp: InvestigationInput, input_ref: dict, spec: RunSpec, services: Services, run_dir: Path, *,
          run_id: str | None = None, authorization: dict | None = None, parent_run: str | None = None,
          faults: set[str] | None = None) -> Outcome:
    run_id = run_id or run_dir.name
    run_dir.mkdir(parents=True, exist_ok=True)
    identity = identity_of(inp, spec.config_sha256, spec.model, spec.condition, spec.mode, input_ref)
    services.store.create_run(run_id, run_dir, identity, parent_run)
    if authorization is not None:
        services.store.set_authorization(run_id, authorization)
    owner = services.store.acquire(run_id)
    rt = _runtime(services, run_id, run_dir, spec, owner, faults)
    rt._input = inp
    initial = {"run_id": run_id, "workflow_version": WORKFLOW_VERSION, "condition": spec.condition,
               "mode": spec.mode.value, "question": inp.question[:2_000], "request": dict(inp.request),
               "input_ref": input_ref, "identity": identity, "required": []}
    validate_state(initial)
    return _drive(services, rt, initial)


def check_identity(services: Services, run_id: str, spec: RunSpec, state: dict) -> None:
    """Block resume if the code version, config, model, protocol, or stored identity changed."""
    stored = json.loads(services.store.run(run_id)["identity_json"])
    current = {"workflow_version": WORKFLOW_VERSION, "config_sha256": spec.config_sha256, "model": spec.model,
               "prompt_version": PROMPT_VERSION, "critic_version": CRITIC_VERSION,
               "condition": spec.condition, "mode": spec.mode.value}
    for key, value in current.items():
        if stored.get(key) != value:
            raise ResumeBlocked(f"{key} changed since the run started ({stored.get(key)!r} -> {value!r}); "
                                "start a new run with --parent instead")
    if state.get("identity") != stored:
        raise ResumeBlocked("checkpoint identity does not match the run record")


def resume(run_id: str, spec: RunSpec, services: Services, *, decision: dict | None = None,
           force_unlock: bool = False, faults: set[str] | None = None) -> Outcome:
    row = services.store.run(run_id)
    run_dir = Path(row["run_dir"])
    if row["status"] not in RESUMABLE:
        return Outcome(run_id, run_dir, row["status"], row["status_reason"], None)
    snapshot = build(_runtime(services, run_id, run_dir, spec, "", None)).compile(
        checkpointer=services.saver).get_state({"configurable": {"thread_id": run_id}})
    if not snapshot.values:
        raise ResumeBlocked(f"no checkpoint found for run {run_id}")
    validate_state(snapshot.values)
    check_identity(services, run_id, spec, snapshot.values)
    owner = services.store.acquire(run_id, force=force_unlock)
    rt = _runtime(services, run_id, run_dir, spec, owner, faults)
    waiting = any(task.interrupts for task in snapshot.tasks)
    payload: object = Command(resume=decision or {}) if waiting else None
    if waiting and decision is None:
        services.store.release(run_id, owner)
        row = services.store.run(run_id)
        return Outcome(run_id, run_dir, "paused", row["status_reason"],
                       json.loads(row["pause_json"]) if row["pause_json"] else None)
    return _drive(services, rt, payload)


def approval_scope(spec: RunSpec, state_identity: dict, hours: float = 24.0) -> dict:
    """The scope granted by --allow-paid: this model, data, protocol, tools, and cost ceiling only."""
    fake_rt = type("R", (), {"limits": spec.limits})()
    scope = expected_scope(fake_rt, {"identity": state_identity})
    return scope | {"expires_utc": (datetime.now(UTC) + timedelta(hours=hours)).isoformat(),
                    "granted_utc": datetime.now(UTC).isoformat(), "grant_id": uuid.uuid4().hex}


def status(services: Services, run_id: str) -> dict:
    row = services.store.run(run_id)
    path = Path(row["run_dir"]) / "workflow_status.json"
    published = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return published | {"run_id": run_id, "status": row["status"], "reason": row["status_reason"],
                        "stage": row["stage"], "pause": json.loads(row["pause_json"]) if row["pause_json"] else None,
                        "locked": bool(row["lock_owner"]), "cancel_requested": bool(row["cancel_requested"]),
                        "parent_run": row["parent_run"]}


__all__ = ["Outcome", "RunLocked", "RunSpec", "Services", "approval_scope", "open_services", "resume", "start",
           "status"]
