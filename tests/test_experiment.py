"""Experiment checks against hand-computed answers and independent implementations."""

from __future__ import annotations

import random
import statistics
import time
from fractions import Fraction

import networkx as nx
import pytest

from blackgrid.evaluation.benchmark import dev_cases
from blackgrid.contracts import EdgeRemovalSensitivity, ExperimentSpec
from blackgrid.analysis.experiment import (
    Analysis,
    DeadlineExceeded,
    _quantile,
    analyse,
    best_modularity,
    derive_seed,
    double_edge_swap,
    modularity,
    profile,
    run_community_test,
    verdict,
)


def spec(**overrides) -> ExperimentSpec:
    fields = dict(
        experiment_id="t", graph_id="g", status="exploratory", hypothesis="h", competing_explanations=("c",),
        task="community_structure_vs_null", method="louvain", statistic="modularity",
        null_model="degree_preserving_double_edge_swap", null_replicates=19, seed=7,
        sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=0.1, replicates=20),
    )
    fields.update(overrides)
    return ExperimentSpec(**fields)


def barbell() -> nx.Graph:
    """Two triangles joined by one bridge: m = 7, each side has total degree 7."""
    return nx.Graph([(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5), (2, 3)])


# --- modularity oracle --------------------------------------------------------------------------


def test_modularity_hand_computed_values():
    # Q = 2 * (3/7 - (7/14)^2) = 5/14
    assert modularity(barbell(), [{0, 1, 2}, {3, 4, 5}]) == pytest.approx(float(Fraction(5, 14)), abs=1e-15)
    # Two disjoint triangles: Q = 2 * (3/6 - (6/12)^2) = 1/2
    two = nx.Graph([(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5)])
    assert modularity(two, [{0, 1, 2}, {3, 4, 5}]) == pytest.approx(0.5, abs=1e-15)
    # One community containing every node: Q = 1 - 1 = 0
    assert modularity(barbell(), [set(range(6))]) == pytest.approx(0.0, abs=1e-15)


def test_modularity_matches_networkx_on_random_partitions():
    rng = random.Random(0)
    for case in dev_cases().values():
        graph = case.graph
        for _ in range(10):
            k = rng.randint(1, 6)
            labels = {n: rng.randrange(k) for n in graph}
            parts = [{n for n in graph if labels[n] == c} for c in range(k)]
            parts = [p for p in parts if p]
            assert modularity(graph, parts) == pytest.approx(nx.community.modularity(graph, parts), abs=1e-12)


def test_louvain_best_of_restarts_finds_known_optimum():
    assert best_modularity(barbell(), 1, "x", restarts=5) == pytest.approx(5 / 14, abs=1e-12)


def test_derived_seeds_are_stable_and_label_sensitive():
    assert derive_seed(1, "null", 3) == derive_seed(1, "null", 3)
    assert len({derive_seed(1, "null", r) for r in range(100)}) == 100
    assert derive_seed(1, "a") != derive_seed(2, "a")


# --- null model ---------------------------------------------------------------------------------


def test_swaps_preserve_degrees_and_simplicity():
    graph = dev_cases()["dev-003"].graph
    null, outcome = double_edge_swap(graph, 1_000, 100_000, random.Random(5))
    assert outcome.reached_target and outcome.accepted == 1_000
    assert dict(null.degree()) == dict(graph.degree())
    assert nx.number_of_selfloops(null) == 0 and null.number_of_edges() == graph.number_of_edges()
    assert set(map(frozenset, null.edges())) != set(map(frozenset, graph.edges()))


def test_swaps_are_deterministic_per_seed():
    graph = dev_cases()["dev-001"].graph
    a, _ = double_edge_swap(graph, 500, 50_000, random.Random(9))
    b, _ = double_edge_swap(graph, 500, 50_000, random.Random(9))
    assert sorted(map(sorted, a.edges())) == sorted(map(sorted, b.edges()))


def test_star_admits_no_valid_swap():
    null, outcome = double_edge_swap(nx.star_graph(20), 10, 1_000, random.Random(1))
    assert outcome.accepted == 0 and not outcome.reached_target and outcome.attempts == 1_000


# --- inference ----------------------------------------------------------------------------------


def test_quantile_matches_statistics_module():
    data = sorted(random.Random(3).random() for _ in range(57))
    cuts = statistics.quantiles(data, n=20, method="inclusive")
    assert _quantile(data, 0.05) == pytest.approx(cuts[0])
    assert _quantile(data, 0.95) == pytest.approx(cuts[-1])
    assert _quantile(data, 0.5) == pytest.approx(statistics.median(data))


def test_completed_analysis_is_internally_consistent():
    graph = dev_cases()["dev-002"].graph
    a = analyse(graph, spec(), "whole_graph", time.perf_counter() + 60)
    r = a.result
    assert a.suitable and r.null_replicates == 19
    assert r.p_value == (1 + r.exceedances) / (1 + r.null_replicates)
    assert r.null.q05 <= r.null.q50 <= r.null.q95
    assert a.delta_q == pytest.approx(r.observed_statistic - r.null.mean)


def test_strong_planted_structure_beats_null_at_minimum_p():
    a = analyse(dev_cases()["dev-001"].graph, spec(), "whole_graph", time.perf_counter() + 60)
    assert a.result.exceedances == 0 and a.result.p_value == pytest.approx(1 / 20)
    assert a.delta_q > 0


# --- abstention and failure ---------------------------------------------------------------------


def test_small_graph_abstains_before_optimizing():
    a = analyse(barbell(), spec(), "whole_graph", time.perf_counter() + 60)
    assert not a.suitable and a.result.outcome == "abstained"
    assert any(r.startswith("S1") for r in a.unsuitable_reasons)
    assert any(r.startswith("S2") for r in a.unsuitable_reasons)


def test_star_abstains_because_null_chain_is_stuck():
    a = analyse(nx.star_graph(25), spec(), "whole_graph", time.perf_counter() + 60)
    assert not a.suitable and any(r.startswith("S3") for r in a.unsuitable_reasons)
    assert a.null_failed == 19


def test_deadline_aborts():
    with pytest.raises(DeadlineExceeded):
        analyse(dev_cases()["dev-002"].graph, spec(), "whole_graph", time.perf_counter() - 1)


def test_oversized_graph_rejected():
    big = nx.gnm_random_graph(1_001, 2_000, seed=1)
    with pytest.raises(ValueError, match="size limits"):
        run_community_test(big, spec(), spec_sha256="x")


# --- verdict rule and full run ------------------------------------------------------------------


def _analysis(suitable: bool, p: float | None) -> Analysis:
    from blackgrid.contracts import ExperimentResult, NullSummary

    if not suitable:
        result = ExperimentResult(experiment_id="x", outcome="abstained", reason="S1")
    else:
        e = round(p * 20) - 1
        result = ExperimentResult(
            experiment_id="x", outcome="completed", observed_statistic=0.5,
            null=NullSummary(mean=0.3, sd=0.1, q05=0.2, q50=0.3, q95=0.4), null_replicates=19, exceedances=e,
            p_value=(1 + e) / 20,
        )
    return Analysis(scope="whole_graph", suitable=suitable, result=result, nodes=10, edges=20)


@pytest.mark.parametrize("primary,secondary,connected,expected", [
    ((False, None), None, True, "abstain"),
    ((True, 0.5), None, True, "not_supported"),
    ((True, 0.05), None, True, "supported"),
    ((True, 0.05), (True, 0.05), False, "supported"),
    ((True, 0.05), (True, 0.5), False, "inconclusive"),
    ((True, 0.05), (False, None), False, "inconclusive"),
    ((True, 0.5), (True, 0.05), False, "not_supported"),
])
def test_verdict_rule(primary, secondary, connected, expected):
    sec = _analysis(*secondary) if secondary else None
    assert verdict(_analysis(*primary), sec, connected, 0.05) == expected


def test_full_run_is_reproducible_and_flags_disconnection():
    graph = dev_cases()["dev-005"].graph
    a = run_community_test(graph, spec(), spec_sha256="x")
    b = run_community_test(graph, spec(), spec_sha256="x")
    assert a.model_dump(exclude={"elapsed_s"}) == b.model_dump(exclude={"elapsed_s"})
    assert "disconnected" in a.flags and a.secondary is not None
    assert a.secondary.scope == "largest_component" and not a.secondary.suitable  # 8-node piece fails S1


def test_profile_counts():
    p = profile(nx.Graph([(0, 1), (1, 2), (3, 4)]))
    assert (p.nodes, p.edges, p.components, p.largest_component_nodes, p.largest_component_edges) == (5, 3, 2, 3, 2)
    assert (p.degree_min, p.degree_max) == (1, 2)
