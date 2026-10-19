"""Scientific invariants and bounded structural workflow acceptance."""
import json
import time

import networkx as nx
import pytest

from blackgrid.agent.roles import Controller, InvestigationInput, flatten
from blackgrid.evaluation.benchmark import dev_cases
from blackgrid.agent.budget import BudgetLedger, FREE
from blackgrid.contracts import BudgetLimits, ExecutionMode
from blackgrid.agent.inquiry import family, safe_outputs, validate_structural
from blackgrid.evaluation.pilot import dev_spec
from blackgrid.agent.providers import MockProvider
from blackgrid.analysis.structural import NodeRow, bridges, centrality, compute, partition, spearman, top_set
from blackgrid.agent.tools import AnswerKeyAccess, ToolContext, ToolRejected, execute


def input_for(kind="centrality", question="Which nodes have many contacts and shortest-path positions?"):
    case = dev_cases()["dev-002"]
    public, graph, record = case.planner_view()
    return InvestigationInput(case_id=public.case_id, question=question, request={"family": kind, "method": "auto"},
                              graph=graph, record=record, spec=dev_spec(case))


@pytest.mark.parametrize("graph", [nx.star_graph(5), nx.path_graph(5), nx.disjoint_union(nx.path_graph(4), nx.empty_graph(2)),
                                       nx.empty_graph(0), nx.empty_graph(4), nx.cycle_graph(5)])
def test_betweenness_matches_independent_networkx_reference(graph):
    rows, summary = centrality(graph, 7, time.perf_counter()+10)
    expected = nx.betweenness_centrality(graph, normalized=True)
    for row in rows:
        assert row.betweenness == pytest.approx(expected[int(row.node)])
        assert row.degree == graph.degree(int(row.node))
    assert not summary["approximate"]


def test_known_star_center_and_ties():
    rows, _ = centrality(nx.star_graph(5), 1, time.perf_counter()+10)
    by_node = {r.node: r for r in rows}
    assert by_node["0"].betweenness == pytest.approx(1)
    assert by_node["0"].degree_rank == 1
    assert {r.degree_rank for r in rows if r.node != "0"} == {2}
    assert top_set({"a": 5, "b": 4, "c": 3, "d": 2, "e": 1, "f": 1}) == set("abcdef")


def test_bridge_formula_on_supplied_partition():
    graph = nx.Graph([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 5), (5, 3)])
    graph.add_node(6)
    supplied = [NodeRow(node=str(n), degree=graph.degree(n), community=0 if n < 3 else 1) for n in graph]
    rows, _ = bridges(graph, supplied)
    by_node = {r.node: r for r in rows}
    assert by_node["2"].cross_degree == by_node["3"].cross_degree == 1
    assert by_node["2"].cross_fraction == pytest.approx(1/3)
    assert by_node["6"].cross_fraction == 0
    assert by_node["0"].cross_degree == 0


def test_partition_covers_nodes_and_is_reproducible():
    graph = nx.disjoint_union(nx.complete_graph(4), nx.empty_graph(2))
    a, meta = partition(graph, 11, time.perf_counter()+10)
    b, _ = partition(graph, 11, time.perf_counter()+10)
    assert a == b and len(a) == len(graph)
    assert len({r.community for r in a if r.degree == 0}) == 2
    assert meta["interpretation"] == "descriptive_partition_not_statistical_support"


def test_sensitivity_keeps_nodes_and_unknown_semantics():
    graph = nx.star_graph(11)
    base = compute("node_centrality", graph, "x", 7, 10, {})
    result = compute("ranking_sensitivity", graph, "x", 7, 10, {"node_centrality.json": base})
    assert result["nodes"] == 12
    assert result["summary"]["removed_pair_status"] == "unknown"
    assert result["summary"]["removed_edges_per_replicate"] == 1
    assert 0 <= result["summary"]["mean_top_jaccard"] <= 1
    assert spearman({"a": 1, "b": 1}, {"a": 2, "b": 3}) is None


def test_prerequisite_and_argument_rejection():
    inp = input_for()
    ctx = ToolContext(inp.graph, inp.record, inp.spec)
    with pytest.raises(ToolRejected, match="prerequisite"):
        execute({"tool": "community_bridge", "args": {}}, ctx)
    with pytest.raises(ToolRejected):
        execute({"tool": "node_centrality", "args": {"arbitrary_code": "no"}}, ctx)
    with pytest.raises(AnswerKeyAccess):
        execute({"tool": "node_centrality", "args": {"answer_key": "no"}}, ctx)


def test_structural_cache_identity_and_corruption(tmp_path):
    inp = input_for()
    def context(): return ToolContext(inp.graph, inp.record, inp.spec, cache_dir=tmp_path)
    first = execute({"tool": "node_centrality", "args": {}}, context()).output
    cached = context()
    assert execute({"tool": "node_centrality", "args": {}}, cached).output == first
    assert cached.calls[-1].cached
    path = next(tmp_path.glob("*.json"))
    entry = json.loads(path.read_text()); entry["payload"]["nodes"] = 777
    path.write_text(json.dumps(entry))
    ctx = context()
    assert execute({"tool": "node_centrality", "args": {}}, ctx).output == first
    assert ctx.calls[-1].cache_rejected


@pytest.mark.parametrize("kind,question,expected", [
    ("centrality", "Which nodes have many contacts?", {"node_centrality", "ranking_sensitivity"}),
    ("bridge", "Which nodes connect groups and are the rankings stable?", {"community_partition", "community_bridge", "ranking_sensitivity"}),
])
def test_complete_structural_workflow_without_community_test(tmp_path, kind, question, expected):
    inp = input_for(kind, question)
    ledger = BudgetLedger(BudgetLimits(), FREE, ExecutionMode.MOCK)
    result, ctx = Controller(MockProvider(), ledger, ExecutionMode.MOCK, tmp_path).investigate(inp, "validated")
    assert result.status.value == "completed", result.failure_reason
    assert {c.tool for c in result.tool_calls} == expected
    assert result.family == kind and result.reported_claims
    assert result.cost.actual_usd == 0
    assert "rows" not in json.dumps(safe_outputs(ctx.outputs))
    assert not any("#/rows/" in path for path in flatten(safe_outputs(ctx.outputs)))


def test_unknown_prose_is_not_accepted(tmp_path):
    provider = MockProvider(script={"analyst": [json.dumps({"verdict": "supported", "claims": [
        {"text": "These people are important.", "evidence": ["node_centrality.json#/summary/max_degree"], "evidence_level": "descriptive"}]})]})
    inp=input_for()
    inp.request=inp.request | {'summary_mode':'model'}
    result, _ = Controller(provider, BudgetLedger(BudgetLimits(), FREE, ExecutionMode.MOCK), ExecutionMode.MOCK, tmp_path).investigate(inp, "validated")
    assert any(not d.accepted for d in result.critic_decisions)
    assert all(c["text"] != "These people are important." for c in result.reported_claims)


def test_follow_up_cannot_repeat_or_execute_arbitrary_tools(tmp_path):
    provider = MockProvider(script={"follow_up": [json.dumps({"decision": "request_follow_up", "tool_calls": [
        {"tool": "node_centrality", "args": {}}]})]})
    result, _ = Controller(provider, BudgetLedger(BudgetLimits(), FREE, ExecutionMode.MOCK), ExecutionMode.MOCK, tmp_path).investigate(input_for(), "validated")
    assert result.status.value == "failed"
    assert "follow-up" in result.failure_reason


def test_ambiguous_influence_and_invalid_plan():
    assert family("Who is influential?", {"family": "auto"}) == "clarify"
    ok, _, reason = validate_structural("Who is influential?", {"family": "centrality"}, {"decision": "run", "tool_calls": [{"tool": "node_centrality", "args": {}}]})
    assert not ok and 'cannot identify' in reason and not _


@pytest.mark.parametrize("baseline", ["degree-preserving", "degree preserving", "degree–preserving"])
def test_community_null_question_uses_community_workflow(tmp_path, baseline):
    question = f"Is community structure stronger than the {baseline} null, and sensitive to missing edges?"
    assert family(question, {"family": "auto"}) == "community"
    inp = input_for("auto", question)
    inp.spec = inp.spec.model_copy(update={"null_replicates": 19,
        "sensitivity": inp.spec.sensitivity.model_copy(update={"replicates": 1})})
    result, _ = Controller(MockProvider(), BudgetLedger(BudgetLimits(), FREE, ExecutionMode.MOCK),
                           ExecutionMode.MOCK, tmp_path).investigate(inp, "validated")
    assert result.status.value == "completed", result.failure_reason
    assert result.family == "community"
    assert {c.tool.split("[")[0] for c in result.tool_calls} == {"profile_graph", "community_test", "edge_removal_sensitivity"}
    assert result.cost.actual_usd == 0


def test_degree_rank_question_remains_centrality():
    assert family("Which nodes have the highest degree?", {"family": "auto"}) == "centrality"


def test_sampled_betweenness_is_seeded_and_marked():
    graph = nx.path_graph(201)
    a, summary = centrality(graph, 3, time.perf_counter()+20)
    b, _ = centrality(graph, 3, time.perf_counter()+20)
    assert a == b and summary["approximate"] and summary["sample_sources"] == 128


def test_structural_prompts_exclude_node_references(tmp_path):
    class Inspect(MockProvider):
        def complete(self, role, payload, messages, max_tokens):
            assert "PRIVATE_NODE_" not in json.dumps(payload)
            assert not any("#/rows/" in p for p in payload.get("evidence", {}))
            return super().complete(role, payload, messages, max_tokens)
    inp = input_for()
    inp.graph = nx.relabel_nodes(inp.graph, {n: f"PRIVATE_NODE_{n}" for n in inp.graph})
    result, _ = Controller(Inspect(), BudgetLedger(BudgetLimits(), FREE, ExecutionMode.MOCK), ExecutionMode.MOCK, tmp_path).investigate(inp, "validated")
    assert result.status.value == "completed"


def test_follow_up_resume_reuses_durable_llm_receipt(tmp_path):
    from blackgrid.workflow.api import RunSpec, open_services, start, resume
    from blackgrid.workflow.engine import SimulatedCrash
    from collections import Counter
    class Counting(MockProvider):
        def __init__(self): super().__init__(); self.calls = Counter()
        def complete(self, role, payload, messages, max_tokens):
            self.calls[role] += 1
            return super().complete(role, payload, messages, max_tokens)
    inp, provider = input_for(), Counting()
    spec = RunSpec(limits=BudgetLimits(), mode=ExecutionMode.MOCK, condition="validated", max_tokens=2000,
                   model=provider.model, config_sha256="fixture", provider_factory=lambda: provider, loader=lambda ref: inp)
    services = open_services(tmp_path)
    with pytest.raises(SimulatedCrash):
        start(inp, {"kind": "fixture"}, spec, services, tmp_path / "run", run_id="run",
              faults={"after_tool:ranking_sensitivity"})
    services.close()
    services = open_services(tmp_path)
    try:
        result = resume("run", spec, services, force_unlock=True)
    finally:
        services.close()
    assert result.status == "completed"
    assert provider.calls["follow_up"] == 1 and provider.calls["planner"] == 1


def test_follow_up_budget_stops_before_call(tmp_path):
    ledger = BudgetLedger(BudgetLimits(max_llm_calls=1), FREE, ExecutionMode.MOCK)
    result, _ = Controller(MockProvider(), ledger, ExecutionMode.MOCK, tmp_path).investigate(input_for(), "validated")
    assert result.status.value == "budget_exhausted" and result.cost.llm_calls == 1


def test_replay_reproduces_follow_up_and_claims(tmp_path):
    from blackgrid.agent.providers import ReplayProvider
    inp = input_for()
    a, _ = Controller(MockProvider(), BudgetLedger(BudgetLimits(), FREE, ExecutionMode.MOCK), ExecutionMode.MOCK, tmp_path / "a").investigate(inp, "validated")
    b, _ = Controller(ReplayProvider(tmp_path / "a" / "llm_trace.jsonl"), BudgetLedger(BudgetLimits(), FREE, ExecutionMode.REPLAY),
                      ExecutionMode.REPLAY, tmp_path / "b").investigate(inp, "validated")
    assert a.reported_claims == b.reported_claims and a.follow_up == b.follow_up


def test_console_question_is_data_and_cannot_enable_paid_mode(tmp_path):
    from blackgrid.console.server import Console
    console = Console(tmp_path, tmp_path / "cache", tmp_path / "config.json", tmp_path, 8765)
    with pytest.raises(ValueError, match="--allow-paid"):
        console.argv({"action": "start", "question": "Which nodes have high betweenness?", "allow_paid": True, "mode": "live"})
    argv = console.argv({"action": "start", "question": "Which nodes have high betweenness?", "allow_paid": True})
    assert argv[argv.index("--mode")+1] == "mock" and "--allow-paid" not in argv
    assert argv[argv.index("--family")+1] == "auto"
    with pytest.raises(ValueError):
        console.argv({"action": "start", "question": "x"*501})
