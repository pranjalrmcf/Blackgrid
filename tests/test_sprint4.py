"""Sprint 4 regressions R1-R5 (SPRINT_04.md §2). Offline: controlled clocks, tiny graphs, mock providers."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from blackgrid.benchmark import dev_cases
from blackgrid.contracts import EdgeRemovalSensitivity, ExperimentSpec
from blackgrid.critic import CriticContext, critique
from blackgrid.tools import ToolContext, ToolRejected, execute
from blackgrid.workflow.store import OperationStore, RunLocked

from tests.test_workflow import Counting, only_run, start


def spec(**overrides) -> ExperimentSpec:
    fields = dict(experiment_id="t", graph_id="g", status="exploratory", hypothesis="h", competing_explanations=("c",),
                  task="community_structure_vs_null", method="louvain", statistic="modularity",
                  null_model="degree_preserving_double_edge_swap", null_replicates=19, seed=3,
                  sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=0.1, replicates=2))
    return ExperimentSpec(**(fields | overrides))


# --- R1: a live worker keeps its lease through a long tool call ------------------------------------------


def _store_with_run(tmp_path) -> OperationStore:
    store = OperationStore(tmp_path / "ops.sqlite")
    store.create_run("r", tmp_path / "r", {})
    return store


def _age_heartbeat(store: OperationStore, seconds: float, pid: int | None = None) -> None:
    old = (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()
    with store.tx() as c:
        c.execute("UPDATE runs SET heartbeat_utc=?, lock_pid=COALESCE(?, lock_pid) WHERE run_id='r'", (old, pid))


def test_r1_live_owner_is_not_displaced_by_a_long_tool_call(tmp_path):
    store = _store_with_run(tmp_path)
    store.acquire("r")  # held by this (alive) process
    _age_heartbeat(store, 1_201)  # longer than the 900 s threshold: a permitted 1,200 s tool call
    with pytest.raises(RunLocked, match="still running"):
        store.acquire("r")
    store.close()


def test_r1_crashed_owner_can_be_recovered_without_force(tmp_path):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()  # a process that has exited: its pid no longer runs this worker
    store = _store_with_run(tmp_path)
    store.acquire("r")
    _age_heartbeat(store, 5, pid=dead.pid)
    assert store.acquire("r")  # recovery does not depend on elapsed time when the owner is gone
    store.close()


def test_r1_displaced_owner_cannot_publish_a_late_tool_result(tmp_path, monkeypatch):
    import blackgrid.workflow.engine as engine
    from blackgrid.workflow.api import open_services

    original = engine.execute
    taken = {}

    def slow_tool(call, ctx):
        result = original(call, ctx)
        if not taken:  # another worker deliberately takes over while the first tool is "running"
            services = open_services(tmp_path)
            (row,) = services.store.runs()
            taken["owner"] = services.store.acquire(row["run_id"], force=True)
            services.close()
        return result

    monkeypatch.setattr(engine, "execute", slow_tool)
    with pytest.raises(RunLocked):
        start(tmp_path, Counting(), None)
    run_id = only_run(tmp_path)
    services = open_services(tmp_path)
    try:
        ops = services.store.operations(run_id, kind="tool")
        assert ops and all(op.state != "succeeded" for op in ops)  # the late result was not adopted
        assert services.store.run(run_id)["lock_owner"] == taken["owner"]  # the new owner keeps the lease
    finally:
        services.close()
    run_dir = tmp_path / run_id
    assert not any((run_dir / name).exists() for name in ("graph_profile.json", "experiment_report.json"))


# --- R2: accepted method/null choices must be the implemented ones -------------------------------------


@pytest.mark.parametrize("field,value", [("method", "greedy_modularity"), ("null_model", "erdos_renyi_gnm")])
def test_r2_unimplemented_method_or_null_is_rejected_by_the_contract(field, value):
    with pytest.raises(ValidationError):
        spec(**{field: value})


def test_r2_unimplemented_method_is_rejected_by_the_tool_schema(tmp_path):
    case = dev_cases()["dev-001"]
    ctx = ToolContext(graph=case.graph, record=case.record, spec=spec())
    with pytest.raises(ToolRejected, match="invalid arguments"):
        execute({"tool": "community_test", "args": {"method": "greedy_modularity"}}, ctx)


def test_r2_executor_refuses_a_spec_that_bypassed_validation():
    from blackgrid.experiment import run_community_test

    forged = spec().model_copy(update={"null_model": "erdos_renyi_gnm"})  # model_copy skips validation
    with pytest.raises(ValueError, match="not implemented"):
        run_community_test(dev_cases()["dev-001"].graph, forged, spec_sha256="x")


# --- R3: cache entries are validated before they become evidence ---------------------------------------


@pytest.fixture
def cached_ctx(tmp_path):
    case = dev_cases()["dev-001"]

    def make() -> ToolContext:
        return ToolContext(graph=case.graph, record=case.record, spec=spec(), cache_dir=tmp_path / "cache")
    first = make()
    execute({"tool": "profile_graph", "args": {}}, first)
    (entry,) = (tmp_path / "cache").glob("*.json")
    return make, entry, first.outputs["graph_profile.json"]


def _edit(entry, fn) -> None:
    data = json.loads(entry.read_text(encoding="utf-8"))
    fn(data)
    entry.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("damage", [
    lambda d: d["payload"].__setitem__("nodes", 777),  # altered count, hash not updated
    lambda d: d.__setitem__("key", "0" * 64),  # wrong computation identity
    lambda d: d.__setitem__("cache_version", 1),  # stale version
])
def test_r3_altered_or_stale_cache_entries_are_rejected_and_recomputed(cached_ctx, damage):
    make, entry, truth = cached_ctx
    _edit(entry, damage)
    ctx = make()
    execute({"tool": "profile_graph", "args": {}}, ctx)
    assert ctx.outputs["graph_profile.json"] == truth and ctx.calls[-1].cached is False
    assert ctx.calls[-1].cache_rejected  # the rejection is recorded, not silent
    assert list(entry.parent.glob("*.rejected-*"))  # diagnostics preserved


def test_r3_consistent_but_wrong_payload_fails_the_invariant_check(cached_ctx):
    """Even a re-hashed edit is caught when it contradicts the graph it claims to describe."""
    import hashlib

    make, entry, truth = cached_ctx

    def forge(d):
        d["payload"]["nodes"] = 777
        d["payload_sha256"] = hashlib.sha256(json.dumps(d["payload"], sort_keys=True).encode()).hexdigest()
    _edit(entry, forge)
    ctx = make()
    execute({"tool": "profile_graph", "args": {}}, ctx)
    assert ctx.outputs["graph_profile.json"]["nodes"] == truth["nodes"] and ctx.calls[-1].cache_rejected


@pytest.mark.parametrize("content", [b"{not json", b""])  # malformed, or an interrupted write
def test_r3_malformed_cache_files_are_rejected(cached_ctx, content):
    make, entry, truth = cached_ctx
    entry.write_bytes(content)
    ctx = make()
    execute({"tool": "profile_graph", "args": {}}, ctx)
    assert ctx.outputs["graph_profile.json"] == truth and ctx.calls[-1].cache_rejected


def test_r3_valid_cache_hit_matches_uncached_execution(cached_ctx):
    make, _, truth = cached_ctx
    hit = make()
    execute({"tool": "profile_graph", "args": {}}, hit)
    assert hit.calls[-1].cached is True and hit.calls[-1].cache_rejected is None
    assert hit.outputs["graph_profile.json"] == truth


def test_r3_writes_leave_no_partial_entry(cached_ctx):
    _, entry, _ = cached_ctx
    assert not list(entry.parent.glob("*.tmp"))


# --- R4: strength wording and comparisons need operational support --------------------------------------


E = "experiment_report.json#/primary/"
EVIDENCE = {E + "result/observed_statistic": 0.265, E + "result/null/mean": 0.199, E + "result/p_value": 0.01,
            E + "delta_q": 0.066, "experiment_report.json#/verdict": "supported"}
SUPPORTED = CriticContext(evidence=EVIDENCE, verdict="supported", delta_q=0.066, p_value=0.01, alpha=0.05)


def claim(text, *links):
    return {"text": text, "evidence_level": "descriptive", "evidence": list(links)}


def test_r4_strength_adjective_is_not_supported_by_a_null_test():
    decision = critique(claim("There is strong community structure (Q = 0.265).", E + "result/observed_statistic"),
                        SUPPORTED)
    assert not decision.accepted and any(r.startswith("R8") for r in decision.reasons)


def test_r4_comparison_must_cite_both_sides():
    one_side = critique(claim("Observed Q = 0.265 exceeds the null.", E + "result/observed_statistic"), SUPPORTED)
    assert not one_side.accepted and any(r.startswith("R7") for r in one_side.reasons)
    both = critique(claim("Observed Q = 0.265 exceeds the null mean 0.199 (p = 0.01).", E + "result/observed_statistic",
                          E + "result/null/mean", E + "result/p_value"), SUPPORTED)
    assert both.accepted, both.reasons


def test_r4_qualified_and_negative_findings_remain_expressible():
    negative = CriticContext(evidence=EVIDENCE, verdict="not_supported", delta_q=-0.01, p_value=0.7, alpha=0.05)
    assert critique(claim("Observed Q does not exceed the null mean (p = 0.01).", E + "result/p_value",
                          E + "result/null/mean"), negative).accepted
    assert critique(claim("Community structure is stronger than the degree-preserving null (p = 0.01).",
                          E + "result/p_value", E + "result/null/mean", E + "result/observed_statistic"),
                    SUPPORTED).accepted


# --- R5: an interrupted suite never stays labelled "running" -------------------------------------------


def test_r5_keyboard_interrupt_leaves_an_accurate_terminal_status(tmp_path, monkeypatch):
    from blackgrid import sprint3

    def interrupt(*_a, **_k):
        raise KeyboardInterrupt
    monkeypatch.setattr(sprint3, "public_registry", interrupt)
    with pytest.raises(KeyboardInterrupt):
        sprint3.run_suite(tmp_path / "suite")
    record = json.loads((tmp_path / "suite" / "suite.json").read_text(encoding="utf-8"))
    assert record["status"] == "interrupted" and record["status"] != "running"
    assert record["errors"][-1]["error"].startswith("KeyboardInterrupt")


def test_r5_interrupted_investigation_is_resumable_not_running(tmp_path, monkeypatch):
    import blackgrid.workflow.engine as engine
    from blackgrid.runner import resume_investigation
    from blackgrid.workflow.api import open_services

    original = engine.execute
    fired = {}

    def interrupt_once(call, ctx):
        if not fired:
            fired["yes"] = True
            raise KeyboardInterrupt
        return original(call, ctx)
    monkeypatch.setattr(engine, "execute", interrupt_once)
    with pytest.raises(KeyboardInterrupt):
        start(tmp_path, Counting(), None)
    run_id = only_run(tmp_path)
    services = open_services(tmp_path)
    try:
        row = services.store.run(run_id)
        assert row["status"] == "paused" and row["lock_owner"] is None and "interrupted" in row["status_reason"]
    finally:
        services.close()
    shown = json.loads((tmp_path / run_id / "workflow_status.json").read_text(encoding="utf-8"))
    assert shown["status"] == "paused" and shown["pause"]["kind"] == "interrupted"
    done = resume_investigation(run_id, tmp_path, provider=Counting(), cache_dir=None)
    assert done.outcome.status == "completed"


def test_tool_descriptions_match_the_configured_run():
    """The planner is told the replicates that will actually run (SPRINT_04.md Session 5, item 6)."""
    from pathlib import Path

    from blackgrid.contracts import RunConfig
    from blackgrid.tools import tool_descriptions

    root = Path(__file__).resolve().parents[1] / "configs"
    full = RunConfig.model_validate_json((root / "collegemsg_full.json").read_text(encoding="utf-8"))
    window = RunConfig.model_validate_json((root / "collegemsg_sprint01.json").read_text(encoding="utf-8"))
    assert "5 replicates with 19 nulls" in tool_descriptions(full.experiment, 19)["edge_removal_sensitivity"]
    assert f"{window.experiment.sensitivity.replicates} replicates with 99 nulls" in \
        tool_descriptions(window.experiment)["edge_removal_sensitivity"]
