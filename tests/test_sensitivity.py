"""Day 6: missing-edge semantics, exp-v1.1 rules A/B, and the sensitivity analysis."""

from __future__ import annotations

import random

import networkx as nx
import pytest

from blackgrid.benchmark import dev_cases
from blackgrid.contracts import EdgeRemovalSensitivity, EdgeStatus, ExperimentSpec
from blackgrid.experiment import run_community_test
from blackgrid.sensitivity import R_SENS, ReplicateSummary, remove_edges, run_replicate, summarise


def spec(**overrides) -> ExperimentSpec:
    fields = dict(experiment_id="s", graph_id="g", status="exploratory", hypothesis="h", competing_explanations=("c",),
                  task="community_structure_vs_null", method="louvain", statistic="modularity",
                  null_model="degree_preserving_double_edge_swap", null_replicates=19, seed=3,
                  sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=0.1, replicates=3))
    fields.update(overrides)
    return ExperimentSpec(**fields)


def test_removal_keeps_nodes_and_is_seeded():
    graph = dev_cases()["dev-001"].graph
    a, removed = remove_edges(graph, 0.1, random.Random(1))
    b, removed_b = remove_edges(graph, 0.1, random.Random(1))
    assert len(removed) == round(0.1 * graph.number_of_edges()) and removed == removed_b
    assert set(a.nodes()) == set(graph.nodes())
    assert not any(a.has_edge(u, v) for u, v in removed)
    assert a.number_of_edges() == graph.number_of_edges() - len(removed)


def test_removed_pairs_are_recorded_as_unknown_not_non_links():
    graph = dev_cases()["dev-001"].graph
    report, summary = run_replicate(graph, spec(), 0)
    counts = summary.edge_status_counts
    assert counts[EdgeStatus.UNKNOWN] == summary.removed_edges > 0
    assert EdgeStatus.KNOWN_NON_LINK not in counts
    assert "incomplete_observation" in report.flags
    assert report.primary.result.null_replicates == R_SENS


def test_rule_a_downgrades_supported_when_pairs_are_unobserved():
    graph = dev_cases()["dev-001"].graph
    full = run_community_test(graph, spec(), spec_sha256="x")
    masked = run_community_test(graph, spec(), spec_sha256="x", unknown_pairs=5)
    assert full.verdict == full.raw_verdict == "supported"
    assert masked.raw_verdict == "supported" and masked.verdict == "inconclusive"
    assert "incomplete_observation" in masked.flags and "incomplete_observation" not in full.flags


def test_rule_b_flags_hub_dominated_graphs_only():
    hubs = run_community_test(dev_cases()["dev-003"].graph, spec(), spec_sha256="x")
    flat = run_community_test(nx.random_regular_graph(4, 30, seed=1), spec(), spec_sha256="x")
    assert "degree_confound" in hubs.flags and "degree_confound" not in flat.flags


def test_summary_counts_agreement_on_raw_verdicts():
    runs = [ReplicateSummary(index=i, removed_edges=1, edge_status_counts={EdgeStatus.OBSERVED: 9, EdgeStatus.UNKNOWN: 1},
                             observed_q=0.4 + i / 100, null_mean=0.3, delta_q=0.1, p_value=0.05, lcc_p_value=None,
                             raw_verdict=v, elapsed_s=0.1)
            for i, v in enumerate(["supported", "supported", "not_supported"])]
    s = summarise(spec(), "supported", runs)
    assert (s.agreement, s.replicates) == (2, 3) and abs(s.agreement_fraction - 2 / 3) < 1e-12
    assert s.verdict_counts == {"not_supported": 1, "supported": 2}
    assert s.observed_q_min == pytest.approx(0.4) and s.observed_q_max == pytest.approx(0.42)
    assert "not an uncertainty interval" in s.label
