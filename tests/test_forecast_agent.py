"""Sprint 6 integration: forecasting as agent tools in the durable workflow (offline, scripted roles)."""

from __future__ import annotations

import json

import pytest

import blackgrid.workflow.engine as engine
from blackgrid.agent import InvestigationInput
from blackgrid.benchmark import dev_cases
from blackgrid.inquiry import family, forecast_task
from blackgrid.pilot import dev_spec
from blackgrid.prediction import suite as suite_mod
from blackgrid.prediction.service import PredictionTools
from blackgrid.prediction.synthetic import triadic_stream
from blackgrid.providers import MockProvider
from blackgrid.runner import run_investigation

from tests.test_workflow import dev_config

NEW_Q = "Which pairs who have never messaged will message in the next few weeks?"
REPEAT_Q = "Which pairs who already talked will message again soon?"


@pytest.fixture(scope="module")
def synthetic_eval(tmp_path_factory):
    events = triadic_stream(seed=9, nodes=60, events=3_000)
    return events, suite_mod.run(events, tmp_path_factory.mktemp("eval") / "sprint6")


@pytest.fixture
def forecast_env(monkeypatch, synthetic_eval):
    events, evaluation = synthetic_eval
    monkeypatch.setattr(engine, "forecast_factory", lambda rt, state, inp: (lambda: PredictionTools(events, evaluation)))
    return events, evaluation


def run(tmp_path, question, provider=None):
    case = dev_cases()["dev-001"]
    public, graph, record = case.planner_view()
    inp = InvestigationInput(case_id="forecast-test", question=question, request={"method": "auto", "family": "auto"},
                             graph=graph, record=record, spec=dev_spec(case))
    return run_investigation(inp, dev_config(), provider or MockProvider(), tmp_path / "runs", cache_dir=None,
                             input_ref={"kind": "dev", "case_id": "dev-001"})


@pytest.mark.parametrize("question,expected", [
    (NEW_Q, "forecast"), (REPEAT_Q, "forecast"), ("Forecast new connections next month", "forecast"),
    ("Will messaging cause new friendships?", "clarify"), ("Who influences others next week?", "clarify"),
    ("Which nodes have many contacts?", "centrality"),
    ("Is community structure stronger than the degree-preserving null?", "community"),
])
def test_forecast_questions_route_to_the_forecast_family(question, expected):
    assert family(question, {"family": "auto"}) == expected


def test_task_follows_the_question():
    assert forecast_task(NEW_Q) == "new_pair" and forecast_task(REPEAT_Q) == "repeat_pair"


def test_agent_runs_forecast_tools_and_checks_claims(tmp_path, forecast_env):
    out = run(tmp_path, NEW_Q)
    inv = json.loads((out.run_dir / "investigation.json").read_text(encoding="utf-8"))
    assert inv["family"] == "forecast" and inv["status"] == "completed", inv.get("failure_reason")
    assert [t["tool"] for t in inv["tool_calls"]] == ["link_prediction", "prediction_compare"]
    assert inv["critic_decisions"] and all(d["accepted"] for d in inv["critic_decisions"])
    ranking = json.loads((out.run_dir / "local_ranking.json").read_text(encoding="utf-8"))
    trace = (out.run_dir / "llm_trace.jsonl").read_text(encoding="utf-8")
    assert ranking and not any(json.dumps(r["pair"]) in trace for r in ranking)  # pairs never reach the model
    assert json.loads((out.run_dir / "link_prediction.json").read_text(encoding="utf-8"))["task"] == "new_pair"
    report = (out.run_dir / "report.md").read_text(encoding="utf-8")
    assert "BLACKGRID forecast" in report and "not probabilities" in report


def test_repeat_question_uses_the_repeat_task(tmp_path, forecast_env):
    out = run(tmp_path, REPEAT_Q)
    assert json.loads((out.run_dir / "link_prediction.json").read_text(encoding="utf-8"))["task"] == "repeat_pair"


@pytest.mark.parametrize("plan", [
    {"decision": "run", "tool_calls": [{"tool": "link_prediction", "args": {"task": "new_pair", "cutoff": 1}}]},
    {"decision": "run", "tool_calls": [{"tool": "community_test", "args": {"method": "louvain"}}]},
    {"decision": "run", "tool_calls": [{"tool": "link_prediction", "args": {"task": "new_pair", "method": "exec(x)"}}]},
])
def test_planner_cannot_move_the_cutoff_or_leave_the_forecast_tools(tmp_path, forecast_env, plan):
    out = run(tmp_path, NEW_Q, MockProvider(script={"planner": [json.dumps(plan)]}))
    inv = json.loads((out.run_dir / "investigation.json").read_text(encoding="utf-8"))
    assert inv["verdict"] == "rejected" and not inv["tool_calls"]


def test_probability_and_scope_violations_are_rejected_by_the_forecast_critic(tmp_path, forecast_env):
    bad = {"verdict": "supported", "flags": [], "claims": [
        {"text": "These pairs have an 80% chance of messaging.", "evidence_level": "descriptive",
         "evidence": ["link_prediction.json#/candidates"], "scope": {"split": "prospective"}},
        {"text": "The forecast covers new students too.", "evidence_level": "descriptive",
         "evidence": ["link_prediction.json#/candidates"], "scope": {"split": "prospective", "task": "repeat_pair"}}]}
    out = run(tmp_path, NEW_Q, MockProvider(script={"analyst": [json.dumps(bad)]}))
    inv = json.loads((out.run_dir / "investigation.json").read_text(encoding="utf-8"))
    first = inv["critic_decisions"][:2]
    assert not first[0]["accepted"] and any(r.startswith("P4") for r in first[0]["reasons"])
    assert not first[1]["accepted"] and any("disagrees with the forecast" in r for r in first[1]["reasons"])
    assert all("80%" not in c["text"] for c in inv["reported_claims"])  # only checked claims are reported


def test_forecast_tools_unavailable_without_a_frozen_evaluation(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "forecast_factory", lambda rt, state, inp: None)
    out = run(tmp_path, NEW_Q)
    inv = json.loads((out.run_dir / "investigation.json").read_text(encoding="utf-8"))
    assert inv["status"] != "completed" and inv["missing_analyses"]
