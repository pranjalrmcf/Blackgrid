"""Sprint 7 evidence tools through the main durable planner/critic workflow."""
from __future__ import annotations

import json
import shutil

import pytest

from blackgrid.agent.inquiry import family, requirements, validate_structural
from blackgrid.agent.providers import MockProvider
from blackgrid.agent.roles import InvestigationInput
from blackgrid.agent.tools import AnswerKeyAccess
from blackgrid.evaluation.benchmark import dev_cases
from blackgrid.evaluation.pilot import dev_spec
from blackgrid.evaluation.sprint7 import run as numerical_run
from blackgrid.workflow import runner
from blackgrid.workflow.engine import SimulatedCrash
from tests.test_workflow import Counting, dev_config, only_run

QUESTION = "Review Sprint 7 uncertainty, posterior beliefs, next experiment and causal identification."


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    root = tmp_path_factory.mktemp("research-source")
    path = root / "runs" / "sprint7-final"
    assert numerical_run(path)["status"] == "completed"
    return root


@pytest.fixture
def environment(monkeypatch, reference):
    monkeypatch.setattr(runner, "REPO_ROOT", reference)


def start(path, question=QUESTION, provider=None, faults=None):
    case = dev_cases()["dev-001"]
    _, graph, record = case.planner_view()
    inp = InvestigationInput(case_id="research-integration", question=question,
                             request={"family": "auto", "method": "auto"}, graph=graph, record=record,
                             spec=dev_spec(case))
    return runner.run_investigation(inp, dev_config(), provider or MockProvider(), path, cache_dir=None,
                                    input_ref={"kind": "dev", "case_id": "dev-001"}, faults=faults)


@pytest.mark.parametrize("question", [QUESTION, "What experiment should I test next?",
                                    "What are the posterior beliefs?", "Show calibration uncertainty.",
                                    "Check causal identification assumptions."])
def test_routes_research_questions(question):
    assert family(question, {"family": "auto"}) == "research"
    assert requirements(question, {"family": "auto"})


def test_end_to_end_main_workflow(environment, tmp_path):
    out = start(tmp_path / "runs")
    assert out.outcome.status == "completed", out.outcome.reason
    inv = json.loads((out.run_dir / "investigation.json").read_text())
    assert inv["family"] == "research"
    assert [c["tool"] for c in inv["tool_calls"]] == ["reliability_audit", "belief_update", "experiment_decision",
                                                       "causal_identification_check"]
    assert inv["reported_claims"] and all(d["accepted"] for d in inv["critic_decisions"])
    assert all(c["origin"] == "synthetic" for c in json.loads((out.run_dir / "manifest.json").read_text())["claims"])
    trace = (out.run_dir / "llm_trace.jsonl").read_text()
    assert "prior_predictive_counts" not in trace and "known_ate" not in trace
    assert "potential outcomes" not in trace
    report = (out.run_dir / "report.md").read_text()
    assert "research evidence review" in report and "saved synthetic" in report
    assert not (out.run_dir / "structural_contract.json").exists()


@pytest.mark.parametrize("call", [
    {"tool": "belief_update", "args": {"success": True}},
    {"tool": "experiment_decision", "args": {"cost": 0}},
    {"tool": "reliability_audit", "args": {"path": "elsewhere"}},
    {"tool": "community_test", "args": {}},
])
def test_research_planner_cannot_submit_outcomes_or_change_settings(call):
    ok, _, _ = validate_structural(QUESTION, {"family": "auto"}, {"decision": "run", "tool_calls": [call]})
    assert not ok


def test_answer_key_attempt_stops_research_plan():
    with pytest.raises(AnswerKeyAccess):
        validate_structural(QUESTION, {"family": "auto"}, {"decision": "run", "tool_calls": [
            {"tool": "belief_update", "args": {"truth": "read"}}]})


def test_critic_rejects_real_world_transfer_and_interval_relabeling(environment, tmp_path):
    bad = {"verdict": "supported", "claims": [{"text": "CollegeMsg users have a 90% probability of interacting.",
            "evidence_level": "descriptive", "evidence": ["belief_update.json#/methods/A/mean"]},
            {"text": "The bootstrap interval is a Bayesian credible interval.", "evidence_level": "descriptive",
             "evidence": ["reliability_audit.json#/bootstrap_confidence_lower"]}]}
    out = start(tmp_path / "runs", provider=MockProvider(script={"analyst": [json.dumps(bad)]}))
    inv = json.loads((out.run_dir / "investigation.json").read_text())
    assert not any(d["accepted"] for d in inv["critic_decisions"][:2])
    assert all("90%" not in c["text"] for c in inv["reported_claims"])


def test_resume_reuses_tools_without_reading_new_observations(environment, tmp_path, reference):
    runs = tmp_path / "runs"
    source_db = reference / "runs" / "sprint7-final" / "belief.sqlite"
    before = source_db.read_bytes()
    first = Counting()
    with pytest.raises(SimulatedCrash):
        start(runs, provider=first, faults={"after_tool:belief_update"})
    second = Counting()
    out = runner.resume_investigation(only_run(runs), runs, provider=second, cache_dir=None, force_unlock=True)
    assert out.outcome.status == "completed", out.outcome.reason
    assert second.calls["planner"] == 0 and second.calls["follow_up"] == 0
    assert source_db.read_bytes() == before
    assert len(out.result.tool_calls) == 4


def test_missing_source_is_partial_not_success(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "REPO_ROOT", tmp_path)
    out = start(tmp_path / "runs")
    assert out.outcome.status == "partial" and out.result.missing_analyses


def test_changed_source_is_rejected_between_steps(monkeypatch, tmp_path, reference):
    root = tmp_path / "source"
    source = root / "runs" / "sprint7-final"
    shutil.copytree(reference / "runs" / "sprint7-final", source)
    monkeypatch.setattr(runner, "REPO_ROOT", root)
    runs = tmp_path / "runs"
    with pytest.raises(SimulatedCrash):
        start(runs, faults={"after_tool:belief_update"})
    manifest = source / "sprint7_manifest.json"
    manifest.write_text(manifest.read_text() + " ")
    out = runner.resume_investigation(only_run(runs), runs, provider=MockProvider(), cache_dir=None, force_unlock=True)
    assert out.outcome.status != "completed" and "experiment_decision" in out.result.missing_analyses


@pytest.mark.parametrize("question,required", [
    ("Is another synthetic experiment worth its cost, or should we stop?",
     ("0.0200 utility units", "net value -0.0200", "no feasible positive net value")),
    ("What causal identification assumptions are satisfied in the saved synthetic study?",
     ("estimand is ATE", "treatment T on outcome Y", "adjustment set is X",
      "no_hidden_confounding=True", "supplied assumptions, not empirically verified")),
])
def test_required_research_explanation_survives_an_omitting_writer(environment, tmp_path, question, required):
    empty = json.dumps({"verdict": "supported", "flags": [], "claims": []})
    out = start(tmp_path / "runs", question, MockProvider(script={"analyst": [empty]}))
    assert out.outcome.status == "completed", out.outcome.reason
    report = (out.run_dir / "report.md").read_text()
    assert all(text in report for text in required)
    from blackgrid.agent.report import check_numbers
    from blackgrid.agent.roles import flatten
    docs = {p.name: json.loads(p.read_text()) for p in out.run_dir.glob('*.json')}
    assert check_numbers(out.report, flatten(docs)) == []


@pytest.mark.parametrize("question,reason", [
    ("Give the exact calibrated probability that a particular pair will message tomorrow.", "tomorrow"),
    ("Use the synthetic posterior to tell me the probability that CollegeMsg has real communities.",
     "success rates under a synthetic model"),
])
def test_real_scope_refusal_is_explicit_and_runs_no_research_tools(environment, tmp_path, question, reason):
    hostile = MockProvider(script={"planner": [json.dumps({"decision":"run", "tool_calls":[
        {"tool":"belief_update", "args":{}}]})]})
    out = start(tmp_path / "runs", question, hostile)
    assert out.result.verdict == "rejected" and not out.result.tool_calls
    assert not out.result.llm_calls
    assert not out.result.reported_claims
    assert reason in (out.run_dir / "report.md").read_text()
