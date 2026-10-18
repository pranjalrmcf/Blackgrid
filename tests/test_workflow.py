"""Sprint 2: the durable workflow under crashes, pauses, authorization, cancellation, and tampering.

Every test is offline (mock or instrumented fake providers). A "new process" is simulated by
closing every database connection and resuming with fresh services and a fresh provider object;
a SimulatedCrash propagates out exactly like a process dying (lock and state left as they were).
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from blackgrid.evaluation.benchmark import dev_cases
from blackgrid.agent.budget import Pricing
from blackgrid.contracts import BudgetLimits, ExecutionMode, RunConfig, RunStatus
from blackgrid.evaluation.pilot import dev_spec
from blackgrid.agent.providers import MockProvider, ProviderError
from blackgrid.workflow.runner import resume_investigation, run_investigation
from blackgrid.workflow.api import open_services
from blackgrid.workflow.engine import ResumeBlocked, SimulatedCrash
from blackgrid.workflow.store import RunLocked

PRICE = Pricing(model="fake-live", prompt_usd_per_token=1e-7, completion_usd_per_token=3e-7, source="test",
                fetched_utc="t")


class Counting(MockProvider):
    """The scripted mock, counting how many times each role really reached the 'provider'."""

    def __init__(self, live: bool = False, **kw) -> None:
        super().__init__(**kw)
        self.calls: Counter = Counter()
        self.live = live
        if live:
            self.model = "fake-live"

    def pricing(self):
        return PRICE if self.live else super().pricing()

    def complete(self, role, payload, messages, max_tokens):
        self.calls[role] += 1
        return super().complete(role, payload, messages, max_tokens)


@pytest.fixture(scope="session")
def cache_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("tool-cache")  # deterministic tool results, shared across tests


def dev_config(mode: str = "mock", **budget) -> RunConfig:
    data = {"dataset": {"dataset_id": "synthetic-dev", "path": "benchmarks/dev", "sha256": "0" * 64,
                        "source_url": "local-synthetic", "citations": ["BLACKGRID synthetic dev set"],
                        "rights_status": "accepted_local_noncommercial", "rights_decision": "D-019"},
            "mode": mode, "condition": "validated", "question": "q"}
    if mode == "live":
        data["paid_execution_authorized"] = True
        data["llm"] = {"model": "fake-live"}  # the model the fake live provider reports
    if budget:
        data["budget"] = budget
    return RunConfig.model_validate(data)


def start(runs: Path, provider, cache_dir, case="dev-002", config=None, **kw):
    dev = dev_cases()[case]
    public, graph, record = dev.planner_view()
    from blackgrid.agent.roles import InvestigationInput

    inp = InvestigationInput(case_id=public.case_id, question=public.question, request=public.request, graph=graph,
                             record=record, spec=dev_spec(dev))
    return run_investigation(inp, config or dev_config(), provider, runs, cache_dir=cache_dir,
                             input_ref={"kind": "dev", "case_id": case}, **kw)


def only_run(runs: Path) -> str:
    services = open_services(runs)
    try:
        (row,) = services.store.runs()
        return row["run_id"]
    finally:
        services.close()


def llm_ops(runs: Path, run_id: str):
    services = open_services(runs)
    try:
        return services.store.operations(run_id, kind="llm")
    finally:
        services.close()


# --- 1. restart recovery without repeating work ------------------------------------------------------


def test_reference_flow_completes_through_the_graph(tmp_path, cache_dir):
    provider = Counting()
    out = start(tmp_path, provider, cache_dir)
    assert out.outcome.status == "completed" and out.result.verdict == "not_supported"
    assert provider.calls == Counter(planner=1, analyst=1, reviser=1)
    stages = json.loads((out.run_dir / "workflow_status.json").read_text(encoding="utf-8"))
    assert stages["stage"] == "finalize" and stages["status"] == "completed" and stages["missing"] == []
    import re

    page = (out.run_dir / "report.html").read_text(encoding="utf-8")
    boot = json.loads(re.search(r'id="bg-boot">(.*?)</script>', page, re.S).group(1))
    snap = boot["payload"]  # the saved snapshot never shows a stale stage/status
    assert boot["mode"] == "static" and snap["workflow"]["status"] == "completed"
    assert snap["workflow"]["stage"] == "finalize" and snap["summary"]["status"] == "completed"


@pytest.mark.parametrize("fault", ["after_tool:edge_removal_sensitivity", "before_dispatch:analyst",
                                   "after_receipt:analyst", "during_finalize"])
def test_crash_then_resume_in_a_new_process_repeats_nothing(tmp_path, cache_dir, fault):
    first = Counting()
    with pytest.raises(SimulatedCrash):
        start(tmp_path, first, cache_dir, faults={fault})
    run_id = only_run(tmp_path)
    second = Counting()  # a different process: fresh provider, fresh connections
    with pytest.raises(RunLocked):  # the crashed worker's lock is not silently stolen
        resume_investigation(run_id, tmp_path, provider=second, cache_dir=cache_dir)
    out = resume_investigation(run_id, tmp_path, provider=second, cache_dir=cache_dir, force_unlock=True)
    assert out.outcome.status == "completed" and out.result.verdict == "not_supported"
    total = first.calls + second.calls
    assert total == Counter(planner=1, analyst=1, reviser=1), f"{fault}: {dict(total)}"
    assert len(llm_ops(tmp_path, run_id)) == 3  # one durable operation per real call
    assert (out.run_dir / "manifest.json").is_file()


def test_crash_after_dispatch_pauses_for_reconciliation_instead_of_resending(tmp_path, cache_dir):
    first = Counting()
    with pytest.raises(SimulatedCrash):
        start(tmp_path, first, cache_dir, faults={"after_dispatch:analyst"})
    run_id = only_run(tmp_path)
    second = Counting()
    out = resume_investigation(run_id, tmp_path, provider=second, cache_dir=cache_dir, force_unlock=True)
    assert out.outcome.status == "paused" and out.outcome.pause["kind"] == "reconciliation"
    assert second.calls["analyst"] == 0  # the uncertain call was NOT sent again
    again = resume_investigation(run_id, tmp_path, provider=second, cache_dir=cache_dir)
    assert again.outcome.status == "paused" and second.calls["analyst"] == 0  # still waiting for a person
    done = resume_investigation(run_id, tmp_path, provider=second, cache_dir=cache_dir,
                                decision={"decision": "retry"})
    assert done.outcome.status == "completed" and second.calls["analyst"] == 1
    states = [op.state for op in llm_ops(tmp_path, run_id)]
    assert states.count("billing_unknown") == 1  # the uncertain call stays on the books


def test_reconcile_stop_ends_the_run_and_keeps_the_charge(tmp_path, cache_dir):
    with pytest.raises(SimulatedCrash):
        start(tmp_path, Counting(), cache_dir, faults={"after_dispatch:planner"})
    run_id = only_run(tmp_path)
    resume_investigation(run_id, tmp_path, provider=Counting(), cache_dir=cache_dir, force_unlock=True)
    out = resume_investigation(run_id, tmp_path, provider=Counting(), cache_dir=cache_dir,
                               decision={"decision": "stop"})
    assert out.outcome.status == "failed" and "reconciliation" in out.outcome.reason
    assert [op.state for op in llm_ops(tmp_path, run_id)] == ["billing_unknown"]


def test_uncertain_provider_error_pauses_rather_than_retrying(tmp_path, cache_dir):
    class Timeout(Counting):
        def complete(self, role, *a, **k):
            if role == "analyst":
                self.calls[role] += 1
                raise ProviderError("read timed out", "uncertain")
            return super().complete(role, *a, **k)

    provider = Timeout()
    out = start(tmp_path, provider, cache_dir)
    assert out.outcome.status == "paused" and provider.calls["analyst"] == 1


def test_crash_during_revision_does_not_repeat_the_reviser_call(tmp_path, cache_dir):
    """Regression (review 3, item 1): resuming the reviser node must reuse the same revision identity."""
    first = Counting()
    with pytest.raises(SimulatedCrash):
        start(tmp_path, first, cache_dir, faults={"after_receipt:reviser"})
    run_id = only_run(tmp_path)
    second = Counting()
    out = resume_investigation(run_id, tmp_path, provider=second, cache_dir=cache_dir, force_unlock=True)
    assert out.outcome.status == "completed"
    assert (first.calls + second.calls)["reviser"] == 1 and out.result.revisions == 1
    assert [op.name for op in llm_ops(tmp_path, run_id)] == ["planner", "analyst", "reviser"]


@pytest.mark.parametrize("fault,role", [("after_receipt:analyst", "analyst"), ("before_dispatch:reviser", "analyst")])
def test_tampered_llm_receipt_is_never_reused(tmp_path, cache_dir, fault, role):
    """Regression (review 3, item 2): saved LLM replies are hash-checked like tool artifacts."""
    with pytest.raises(SimulatedCrash):
        start(tmp_path, Counting(), cache_dir, faults={fault})
    run_id = only_run(tmp_path)
    (op,) = [o for o in llm_ops(tmp_path, run_id) if o.name == role]
    receipt = next(tmp_path.rglob(f"ops/{op.op_id}.json"))
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data["response"] = data["response"].replace("not_supported", "supported")  # forge a nicer reply
    receipt.write_text(json.dumps(data), encoding="utf-8")
    second = Counting()
    out = resume_investigation(run_id, tmp_path, provider=second, cache_dir=cache_dir, force_unlock=True)
    assert out.outcome.status == "failed" and "integrity" in out.outcome.reason
    assert sum(second.calls.values()) == 0  # no further paid work after the tampering was detected
    status = json.loads(next(tmp_path.rglob("workflow_status.json")).read_text(encoding="utf-8"))
    assert status["status"] == "failed" and (out.run_dir / "manifest.json").is_file()  # failure fully recorded


def test_expired_deadline_still_finalizes_and_persists_the_failure(tmp_path, cache_dir):
    """Regression (review 3, item 3): finalize must run even after the wall-clock deadline."""
    from blackgrid.agent.roles import Controller
    from blackgrid.agent.budget import BudgetLedger
    from blackgrid.contracts import BudgetLimits

    dev = dev_cases()["dev-002"]
    public, graph, record = dev.planner_view()
    from blackgrid.agent.roles import InvestigationInput

    inp = InvestigationInput(case_id=public.case_id, question=public.question, request=public.request, graph=graph,
                             record=record, spec=dev_spec(dev))
    from blackgrid.agent.budget import FREE

    ledger = BudgetLedger(limits=BudgetLimits(), pricing=FREE)
    result, _ = Controller(Counting(), ledger, ExecutionMode.MOCK, tmp_path, deadline_s=0).investigate(inp, "validated")
    assert result.status is RunStatus.FAILED and "deadline" in result.failure_reason
    published = json.loads((tmp_path / "workflow_status.json").read_text(encoding="utf-8"))
    assert published["status"] == "failed" and published["stage"] == "finalize"  # the store agrees


# --- 2. budgets and locks survive restarts -----------------------------------------------------------


def test_call_cap_is_enforced_across_a_restart(tmp_path, cache_dir):
    config = dev_config(max_llm_calls=2)
    with pytest.raises(SimulatedCrash):
        start(tmp_path, Counting(), cache_dir, config=config, faults={"before_dispatch:analyst"})
    run_id = only_run(tmp_path)
    second = Counting()
    out = resume_investigation(run_id, tmp_path, provider=second, cache_dir=cache_dir, force_unlock=True)
    # planner (before the crash) + analyst: the reviser would be call 3, so no revision happens.
    assert out.outcome.status == "completed" and out.result.cost.llm_calls == 2
    assert second.calls == Counter(analyst=1) and out.result.revisions == 0


def test_concurrent_resume_is_rejected(tmp_path, cache_dir):
    with pytest.raises(SimulatedCrash):
        start(tmp_path, Counting(), cache_dir, faults={"before_dispatch:analyst"})
    run_id = only_run(tmp_path)
    services = open_services(tmp_path)
    try:
        services.store.acquire(run_id, force=True)  # another worker takes the run and stays active
        with pytest.raises(RunLocked):
            resume_investigation(run_id, tmp_path, provider=Counting(), cache_dir=cache_dir)
    finally:
        services.close()


def test_sprint1_spend_is_imported_and_the_sprint2_cap_is_separate(tmp_path, cache_dir):
    (tmp_path / "spend_ledger.json").write_text(json.dumps({"total_usd": 9.999}), encoding="utf-8")
    provider = Counting(live=True)
    out = start(tmp_path, provider, cache_dir, config=dev_config("live"), allow_paid=True)
    assert out.outcome.status == "budget_exhausted" and "project USD cap" in out.outcome.reason
    assert sum(provider.calls.values()) == 0  # stopped before any paid call


# --- 3. human control ----------------------------------------------------------------------------------


def test_live_run_pauses_for_authorization_then_resumes_once_approved(tmp_path, cache_dir):
    provider = Counting(live=True)
    out = start(tmp_path, provider, cache_dir, config=dev_config("live"))
    assert out.outcome.status == "paused" and out.outcome.pause["kind"] == "authorization"
    assert sum(provider.calls.values()) == 0  # the planner itself is a paid call: nothing ran
    run_id = out.outcome.run_id
    done = resume_investigation(run_id, tmp_path, provider=provider, cache_dir=cache_dir, allow_paid=True)
    assert done.outcome.status == "completed" and provider.calls["planner"] == 1
    assert done.result.cost.actual_usd > 0


def test_expired_or_mismatched_authorization_pauses_again(tmp_path, cache_dir):
    provider = Counting(live=True)
    with pytest.raises(SimulatedCrash):
        start(tmp_path, provider, cache_dir, config=dev_config("live"), allow_paid=True,
              faults={"before_dispatch:analyst"})
    run_id = only_run(tmp_path)
    services = open_services(tmp_path)
    try:
        scope = services.store.authorization(run_id)
        services.store.set_authorization(run_id, scope | {"expires_utc": (datetime.now(UTC) - timedelta(
            minutes=1)).isoformat()})
    finally:
        services.close()
    paused = resume_investigation(run_id, tmp_path, provider=provider, cache_dir=cache_dir, force_unlock=True)
    assert paused.outcome.status == "paused" and "expired" in paused.outcome.reason
    services = open_services(tmp_path)
    try:
        scope = services.store.authorization(run_id)
    finally:
        services.close()
    wrong = scope | {"model": "some-other-model",
                     "expires_utc": (datetime.now(UTC) + timedelta(hours=1)).isoformat()}
    out = resume_investigation(run_id, tmp_path, provider=provider, cache_dir=cache_dir,
                               decision={"decision": "approve", "scope": wrong})
    assert out.outcome.status == "failed" and "model changed" in out.outcome.reason
    assert provider.calls["analyst"] == 0


def test_cancel_while_paused_and_at_a_node_boundary(tmp_path, cache_dir):
    out = start(tmp_path / "a", Counting(live=True), cache_dir, config=dev_config("live"))
    services = open_services(tmp_path / "a")
    services.store.request_cancel(out.outcome.run_id)
    services.close()
    cancelled = resume_investigation(out.outcome.run_id, tmp_path / "a", provider=Counting(live=True),
                                     cache_dir=cache_dir, decision={"decision": "cancel"})
    assert cancelled.outcome.status == "cancelled" and cancelled.manifest.status is RunStatus.CANCELLED

    with pytest.raises(SimulatedCrash):
        start(tmp_path / "b", Counting(), cache_dir, faults={"before_dispatch:analyst"})
    run_id = only_run(tmp_path / "b")
    services = open_services(tmp_path / "b")
    services.store.request_cancel(run_id)
    services.close()
    provider = Counting()
    out = resume_investigation(run_id, tmp_path / "b", provider=provider, cache_dir=cache_dir, force_unlock=True)
    assert out.outcome.status == "cancelled" and provider.calls["analyst"] == 0


# --- 4. integrity --------------------------------------------------------------------------------------


def test_tampered_artifact_blocks_completion(tmp_path, cache_dir):
    with pytest.raises(SimulatedCrash):
        start(tmp_path, Counting(), cache_dir, faults={"before_dispatch:analyst"})
    run_id = only_run(tmp_path)
    report = next(tmp_path.glob("*/experiment_report.json"))
    data = json.loads(report.read_text(encoding="utf-8"))
    data["verdict"] = "supported"  # forge a nicer answer
    report.write_text(json.dumps(data), encoding="utf-8")
    out = resume_investigation(run_id, tmp_path, provider=Counting(), cache_dir=cache_dir, force_unlock=True)
    assert out.outcome.status == "failed" and "modified" in out.outcome.reason


def test_unknown_checkpoint_version_or_changed_config_blocks_resume(tmp_path, cache_dir):
    with pytest.raises(SimulatedCrash):
        start(tmp_path, Counting(), cache_dir, faults={"before_dispatch:analyst"})
    run_id = only_run(tmp_path)
    run_dir = next(p for p in tmp_path.iterdir() if p.is_dir() and p.name.startswith("2"))
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    config["question"] = "a different question"  # deliberately changed experiment input
    (run_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ResumeBlocked, match="config_sha256 changed"):
        resume_investigation(run_id, tmp_path, provider=Counting(), cache_dir=cache_dir, force_unlock=True)

    conn = sqlite3.connect(tmp_path / "checkpoints.sqlite")
    rows = conn.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id=?", (run_id,)).fetchone()[0]
    conn.close()
    assert rows > 0
    from blackgrid.workflow.engine import validate_state

    with pytest.raises(ResumeBlocked, match="unknown version"):
        validate_state({"run_id": run_id, "workflow_version": "wf-v0", "condition": "validated", "mode": "mock",
                        "question": "q", "request": {}, "input_ref": {}, "identity": {}, "required": []})


def test_checkpoints_and_prompts_hold_no_secrets_identifiers_or_answer_keys(tmp_path, cache_dir, monkeypatch):
    monkeypatch.setenv("OPEN_ROUTER_API_KEY", "sk-or-v1-SECRET-never-store-me")
    start(tmp_path, Counting(), cache_dir, case="dev-006")  # has planted labels and hidden edges
    blobs = [(tmp_path / "checkpoints.sqlite").read_bytes(), (tmp_path / "workflow.sqlite").read_bytes()]
    blobs += [p.read_bytes() for p in tmp_path.rglob("ops/*.json")]
    for blob in blobs:
        for forbidden in (b"SECRET", b"sk-or-v1", b"planted", b"hidden_edges", b"acceptable_verdicts",
                          b"rationale"):
            assert forbidden not in blob, forbidden
    assert os.environ.get("LANGSMITH_TRACING") == "false"  # no external tracing


def test_replay_never_falls_back_to_a_live_call(tmp_path, cache_dir):
    done = start(tmp_path / "rec", Counting(), cache_dir)
    from blackgrid.agent.providers import ReplayProvider

    replay = ReplayProvider(done.run_dir / "llm_trace.jsonl")
    out = start(tmp_path / "rep", replay, cache_dir, case="dev-001")  # different case: prompts won't match
    assert out.outcome.status == "failed" and "ReplayMismatch" in out.outcome.reason


def test_failed_required_sensitivity_is_partial_not_completed(tmp_path, monkeypatch):
    from blackgrid.agent import tools
    from blackgrid.analysis.experiment import DeadlineExceeded

    def slow(*_a, **_k):
        raise DeadlineExceeded("experiment exceeded its tool timeout")

    monkeypatch.setattr(tools, "run_replicate", slow)
    out = start(tmp_path, Counting(), None)  # no cache: really run (and fail) the sensitivity tool
    assert out.outcome.status == "partial" and out.result.missing_analyses == ("edge_removal_sensitivity",)
    assert out.result.reported_claims == ()  # an incomplete answer never reaches analysis
