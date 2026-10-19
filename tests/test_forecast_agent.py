"""Sprint 6 integration: forecasting as agent tools in the durable workflow (offline, scripted roles)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import blackgrid.workflow.engine as engine
from blackgrid.agent.roles import InvestigationInput
from blackgrid.evaluation.benchmark import dev_cases
from blackgrid.agent.inquiry import family, forecast_task
from blackgrid.evaluation.pilot import dev_spec
from blackgrid.prediction import suite as suite_mod
from blackgrid.prediction.service import PredictionTools
from blackgrid.prediction.synthetic import triadic_stream
from blackgrid.agent.providers import MockProvider
from blackgrid.workflow.runner import run_investigation

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
    out = run(tmp_path, NEW_Q)
    inv = json.loads((out.run_dir / "investigation.json").read_text(encoding="utf-8"))
    # Validated forecast summaries are now local. Exercise the same critic directly with hostile prose,
    # rather than asserting that an unnecessary writer request still occurs.
    ctx = SimpleNamespace(outputs={name: json.loads((out.run_dir / name).read_text())
                                  for name in ("link_prediction.json", "prediction_compare.json")})
    first = [engine.forecast_decision(c, ctx) for c in bad["claims"]]
    assert not first[0]["accepted"] and any(r.startswith("P4") for r in first[0]["reasons"])
    assert not first[1]["accepted"] and any("disagrees with the forecast" in r for r in first[1]["reasons"])
    assert all("80%" not in c["text"] for c in inv["reported_claims"])  # only checked claims are reported


def test_forecast_finishes_without_waiting_for_an_interpretation_provider(tmp_path, forecast_env):
    class PlannerOnly(MockProvider):
        def complete(self, role, payload, messages, max_tokens):
            if role != "planner":
                raise AssertionError("Forecast interpretation must not depend on another provider response")
            return super().complete(role, payload, messages, max_tokens)
    out = run(tmp_path, REPEAT_Q, PlannerOnly())
    assert out.outcome.status == "completed"
    assert out.result.reported_claims
    assert [c.role for c in out.result.llm_calls] == ["planner"]
    assert all(d.accepted for d in out.result.critic_decisions)


def test_forecast_tools_unavailable_without_a_frozen_evaluation(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "forecast_factory", lambda rt, state, inp: None)
    out = run(tmp_path, NEW_Q)
    inv = json.loads((out.run_dir / "investigation.json").read_text(encoding="utf-8"))
    assert inv["status"] != "completed" and inv["missing_analyses"]


@pytest.mark.parametrize("question,expected,task", [
    # the exact questions suggested to the user (D-080)
    ("Which pairs who have been messaging recently are most likely to keep talking over the next few weeks, and how "
     "reliable has this ranking been in past windows?", "forecast", "repeat_pair"),
    ("Which people who have never messaged each other are most likely to start in the next three weeks?", "forecast",
     "new_pair"),
    ("Which students connect otherwise separate groups, and are those rankings stable if some messages are missing?",
     "bridge", None),
    ("What is the probability that two specific students will start dating next month?", "forecast", None),
    # more wording variants
    ("Who will start messaging over the coming month?", "forecast", "new_pair"),
    ("Which nodes sit between different communities?", "bridge", None),
    ("Is the network modular?", "community", None),
    ("Why do some students message more than others?", "clarify", None),
])
def test_suggested_and_varied_wording_routes_correctly(question, expected, task):
    assert family(question, {"family": "auto"}) == expected
    if task:
        assert forecast_task(question) == task


def test_clarify_messages_say_what_actually_happened():
    from blackgrid.agent.inquiry import validate_structural

    unmatched = validate_structural("Tell me something interesting.", {"family": "auto"}, {})[2]
    causal = validate_structural("Why do people message?", {"family": "auto"}, {})[2]
    assert "could not match" in unmatched and "causes" not in unmatched
    assert "causes, influence or persuasion" in causal


@pytest.mark.parametrize("question", [
    "Does the observed community structure exceed what the degree sequence alone would explain, and does that "
    "conclusion remain stable when 10% of observed connections are removed?",
    "Does clustering exceed what the degree distribution would explain?",
    "Is modularity unusual given the degree-sequence null?",
])
def test_community_degree_baseline_is_not_node_centrality(question):
    from blackgrid.agent.critic import validate_plan
    request = {"family": "auto", "method": "auto"}
    assert family(question, request) == "community"
    # Exact valid plan recorded in the rejected real-provider run.
    plan = {"decision": "run", "tool_calls": [
        {"tool": "community_test", "args": {"method": "louvain"}},
        {"tool": "edge_removal_sensitivity", "args": {}}]}
    decision = validate_plan(question, request, plan)
    assert decision.allowed
    assert [c["tool"] for c in decision.tool_calls] == ["community_test", "edge_removal_sensitivity"]


def test_degree_baseline_context_does_not_hide_explicit_centrality_or_causal_requests():
    assert family("Which nodes have the highest degree in each community?", {"family": "auto"}) == "centrality"
    assert family("Compare node betweenness within communities given the degree sequence.",
                  {"family": "auto"}) == "centrality"
    assert family("Does degree cause community structure?", {"family": "auto"}) == "clarify"


def test_inapplicable_extra_tool_is_dropped_not_fatal():
    """The exact live plan from D-081: a sound forecast plus ranking_sensitivity for 'how reliable'."""
    from blackgrid.agent.inquiry import validate_forecast

    q = ("Which pairs who have been messaging recently are most likely to keep talking over the next few weeks, and how "
         "reliable has this ranking been in past windows?")
    plan = {"decision": "run", "tool_calls": [
        {"tool": "link_prediction", "args": {"task": "repeat_pair", "method": "selected"}},
        {"tool": "prediction_compare", "args": {"task": "repeat_pair", "split": "rolling"}},
        {"tool": "ranking_sensitivity", "args": {}}]}
    ok, calls, reason = validate_forecast(q, {"family": "auto"}, plan)
    assert ok and [c["tool"] for c in calls] == ["link_prediction", "prediction_compare"]
    assert "Ignored tools that do not apply to forecasts: ranking_sensitivity" in reason
    bad = {"decision": "run", "tool_calls": [{"tool": "shell", "args": {}}]}
    assert validate_forecast(q, {"family": "auto"}, bad)[0] is False  # unregistered tools are still refused
