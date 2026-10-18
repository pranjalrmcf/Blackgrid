"""Day 7 and 12: allowlisted execution, argument validation, guards, and caching."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request

import networkx as nx
import pytest

from blackgrid.analysis import experiment
from blackgrid.evaluation.benchmark import dev_cases
from blackgrid.contracts import EdgeRemovalSensitivity, ExperimentSpec
from blackgrid.analysis.experiment import DeadlineExceeded
from blackgrid.agent.tools import AnswerKeyAccess, NetworkDenied, ToolContext, ToolRejected, execute, network_denied


def spec(**overrides) -> ExperimentSpec:
    fields = dict(experiment_id="t", graph_id="g", status="exploratory", hypothesis="h", competing_explanations=("c",),
                  task="community_structure_vs_null", method="louvain", statistic="modularity",
                  null_model="degree_preserving_double_edge_swap", null_replicates=19, seed=3,
                  sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=0.1, replicates=2))
    fields.update(overrides)
    return ExperimentSpec(**fields)


@pytest.fixture
def ctx(tmp_path) -> ToolContext:
    case = dev_cases()["dev-001"]
    return ToolContext(graph=case.graph, record=case.record, spec=spec(), cache_dir=tmp_path / "cache")


@pytest.mark.parametrize("raw,why", [
    ({"tool": "exec_python", "args": {"code": "print(1)"}}, "not allowlisted"),
    ({"tool": "shell", "args": {}}, "not allowlisted"),
    (["community_test"], "malformed"),
    ({"tool": "community_test", "args": {}, "extra": 1}, "malformed"),
    ({"tool": "community_test", "args": "louvain"}, "malformed"),
    ({"tool": "community_test", "args": {"method": "louvain", "code": "x"}}, "invalid arguments"),
    ({"tool": "community_test", "args": {"method": "spectral"}}, "invalid arguments"),
    ({"tool": "community_test", "args": {"method": "greedy_modularity"}}, "invalid arguments"),  # R2
    ({"tool": "edge_removal_sensitivity", "args": {}}, "prerequisite missing"),
    ({"tool": "profile_graph", "args": {}, "x": "y" * 3000}, "oversized request"),
])
def test_bad_requests_are_rejected_and_recorded(ctx, raw, why):
    with pytest.raises(ToolRejected, match=why):
        execute(raw, ctx)
    assert ctx.calls[-1].outcome == "failed" and ctx.outputs == {}


@pytest.mark.parametrize("raw", [
    {"tool": "read_answer_key", "args": {}},
    {"tool": "profile_graph", "args": {"path": "benchmarks/sealed/test-001.json"}},
    {"tool": "community_test", "args": {"method": "planted_labels"}},
])
def test_answer_key_access_attempts_stop_the_run(ctx, raw):
    with pytest.raises(AnswerKeyAccess):
        execute(raw, ctx)
    assert ctx.calls[-1].error == "answer_key_access_attempt"


def test_oversized_graph_is_refused_before_computation(ctx):
    ctx.graph = nx.gnm_random_graph(1_001, 1_500, seed=1)
    with pytest.raises(ToolRejected, match="oversized graph"):
        execute({"tool": "profile_graph", "args": {}}, ctx)


def test_network_is_denied_inside_tools_and_restored_after():
    original = socket.socket.connect
    with network_denied():
        with pytest.raises(urllib.error.URLError, match="network access is denied"):  # urllib wraps the guard
            urllib.request.urlopen("http://example.com", timeout=1)
        with pytest.raises(NetworkDenied):
            socket.create_connection(("127.0.0.1", 9))
    assert socket.socket.connect is original


def test_timeout_is_recorded_as_a_failed_call(ctx, monkeypatch):
    def too_slow(*_a, **_k):
        raise DeadlineExceeded("experiment exceeded its tool timeout")

    monkeypatch.setattr(experiment, "analyse", too_slow)
    with pytest.raises(ToolRejected, match="DeadlineExceeded"):
        execute({"tool": "community_test", "args": {"method": "louvain"}}, ctx)
    assert "DeadlineExceeded" in ctx.calls[-1].error


def test_valid_sequence_runs_and_second_call_is_cached(ctx, tmp_path):
    execute({"tool": "profile_graph", "args": {}}, ctx)
    first = execute({"tool": "community_test", "args": {"method": "louvain"}}, ctx)
    sens = execute({"tool": "edge_removal_sensitivity", "args": {}}, ctx)
    assert first.output["verdict"] == "supported" and sens.output["replicates"] == 2
    assert sum(c.tool.startswith("edge_removal_sensitivity[") for c in ctx.calls) == 2  # one record per replicate
    again = ToolContext(graph=ctx.graph, record=ctx.record, spec=ctx.spec, cache_dir=tmp_path / "cache")
    second = execute({"tool": "community_test", "args": {"method": "louvain"}}, again)
    assert again.calls[-1].cached and second.output == first.output
