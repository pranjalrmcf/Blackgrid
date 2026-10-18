"""Sprint 6 Sessions 1-3: cutoff safety, candidate universes, known-answer scores and metrics (offline)."""

from __future__ import annotations

import math

import networkx as nx
import pytest

from blackgrid.prediction import scores as S
from blackgrid.prediction.metrics import evaluate, rank_metrics
from blackgrid.prediction.synthetic import triadic_stream
from blackgrid.prediction.temporal import (CapacityExceeded, boundaries, candidate_count, candidates, canonical,
                                           history, horizon_labels, snapshot_manifest, tiebreak)


def events_of(edges, t=100):
    return [(u, v, t + i) for i, (u, v) in enumerate(edges)]


# --- boundaries and cutoff semantics -------------------------------------------------------------------


def test_boundaries_follow_elapsed_time():
    b = boundaries([(0, 1, 100), (1, 2, 199)])  # t0 = 100, t_end = 200, D = 100
    assert b == [100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200]
    with pytest.raises(ValueError):
        boundaries([(0, 1, 5), (1, 2, 6)])  # span 2 s < 10 bins


def test_events_at_the_cutoff_are_future_and_ties_stay_together():
    ev = [(0, 1, 10), (1, 2, 20), (2, 3, 20), (0, 3, 25)]
    hist = history(ev, cutoff=20)
    assert hist.nodes == {0, 1} and hist.events == 1  # both t=20 events are on the future side
    lab = horizon_labels(ev, hist, end=30)
    assert lab.positives == frozenset()  # (1,2),(2,3),(0,3) all involve node 2/3, unseen before t=20
    assert lab.cold_start_pairs == 3


def test_self_loops_repeats_and_reversals():
    ev = [(0, 1, 1), (1, 0, 2), (0, 1, 3), (2, 2, 4), (1, 2, 5)]
    hist = history(ev, cutoff=10)
    assert hist.pair_count[(0, 1)] == 3 and hist.pair_last[(0, 1)] == 3  # reversal = same canonical pair
    assert hist.self_loops_excluded == 1 and (2, 2) not in hist.pair_count
    assert canonical(5, 3) == (3, 5)


def test_future_mutation_cannot_change_history_or_candidates():
    """Alter events at/after the cutoff: features, eligible nodes and candidates must not move."""
    base = triadic_stream(seed=3, nodes=40, events=1_500)
    cut = boundaries(base)[6]
    mutated = [e for e in base if e[2] < cut] + [(e[1], 999, e[2]) for e in base if e[2] >= cut]
    a, b = history(base, cut), history(mutated, cut)
    assert a.fingerprint() == b.fingerprint() and a.nodes == b.nodes
    for task in ("new_pair", "repeat_pair"):
        assert list(candidates(a, task)) == list(candidates(b, task))
        for method in S.methods_for(task):
            batch = list(candidates(a, task))[:500]
            assert method.build(1000)(a, batch) == method.build(1000)(b, batch)
    end = boundaries(base)[7]
    assert horizon_labels(base, a, end) != horizon_labels(mutated, b, end)  # labels may change, as expected


def test_future_positive_beyond_the_horizon_stays_a_zero_label():
    ev = [(0, 1, 1), (1, 2, 2), (0, 2, 50)]
    hist = history(ev, cutoff=10)
    lab = horizon_labels(ev, hist, end=20)
    assert (0, 2) in set(candidates(hist, "new_pair")) and (0, 2) not in lab.positives


# --- candidate universes ----------------------------------------------------------------------------------


def test_two_task_universes_partition_known_pairs():
    hist = history(events_of([(0, 1), (1, 2), (3, 4)]), cutoff=1_000)
    new, rep = set(candidates(hist, "new_pair")), set(candidates(hist, "repeat_pair"))
    assert rep == {(0, 1), (1, 2), (3, 4)} and not new & rep
    assert len(new | rep) == 5 * 4 // 2 and candidate_count(hist, "new_pair") == len(new)


def test_capacity_is_a_recorded_stop_not_sampling(monkeypatch):
    import blackgrid.prediction.temporal as T

    monkeypatch.setattr(T, "MAX_CANDIDATES", 3)
    hist = history(events_of([(0, 1), (2, 3), (4, 5)]), cutoff=1_000)
    with pytest.raises(CapacityExceeded):
        next(candidates(hist, "new_pair"))


def test_manifest_is_aggregate_only():
    ev = triadic_stream(seed=2, nodes=30, events=800)
    b = boundaries(ev)
    hist = history(ev, b[5])
    man = snapshot_manifest(hist, horizon_labels(ev, hist, b[6]), "new_pair")
    assert man.candidates == candidate_count(hist, "new_pair") and 0 <= man.positives <= man.candidates
    dumped = man.model_dump()
    assert all(isinstance(v, (int, float, str)) or v is None for v in dumped.values())  # no lists of pairs/nodes
    assert all(len(v) == 64 for k, v in dumped.items() if k.endswith(("fingerprint", "sha256")))  # hashes only


# --- known-answer structural scores (independent networkx references) ------------------------------------


@pytest.mark.parametrize("graph", [nx.complete_graph(3), nx.path_graph(5), nx.star_graph(4),
                                   nx.disjoint_union(nx.path_graph(3), nx.path_graph(2))])
def test_structural_scores_match_networkx(graph):
    hist = history(events_of(list(graph.edges())), cutoff=10_000)
    pairs = [canonical(u, v) for u, v in nx.non_edges(graph)]
    ref = {
        S.jaccard: {canonical(u, v): s for u, v, s in nx.jaccard_coefficient(graph, pairs)},
        S.adamic_adar: {canonical(u, v): s for u, v, s in nx.adamic_adar_index(graph, pairs)},
        S.resource_allocation: {canonical(u, v): s for u, v, s in nx.resource_allocation_index(graph, pairs)},
        S.preferential_attachment: {canonical(u, v): s for u, v, s in nx.preferential_attachment(graph, pairs)},
    }
    for scorer, expected in ref.items():
        for pair, got in zip(pairs, scorer(hist, pairs)):
            assert math.isclose(got, expected[pair], abs_tol=1e-12), (scorer.__name__, pair)
    cn = {canonical(u, v): len(list(nx.common_neighbors(graph, u, v))) for u, v in pairs}
    assert S.common_neighbors(hist, pairs) == [float(cn[p]) for p in pairs]


def test_zero_denominators_score_zero():
    hist = history(events_of([(0, 1)]), cutoff=1_000)
    # node 5 has never been seen: an empty neighbourhood everywhere
    assert S.jaccard(hist, [(0, 5)]) == [0.0] and S.adamic_adar(hist, [(0, 5)]) == [0.0]
    assert S.preferential_attachment(hist, [(0, 5)]) == [0.0]


def test_temporal_scores_use_only_recent_history():
    ev = [(0, 1, 10), (1, 2, 90), (2, 3, 95)]
    hist = history(ev, cutoff=100)
    assert hist.activity(1, 20) == 1 and hist.activity(0, 20) == 0  # window [80, 100)
    assert S.recent_activity_product(20)(hist, [(1, 3)]) == [1.0 * 1.0]
    assert S.recent_resource_allocation(20)(hist, [(1, 3)]) == [0.5]  # common recent neighbour 2 (degree 2)
    assert S.pair_frequency(hist, [(0, 1)]) == [1.0] and S.pair_recency(hist, [(2, 3)]) == [-5]


def test_pair_methods_are_registered_for_repeat_interactions_only():
    assert {m.name for m in S.methods_for("new_pair")}.isdisjoint({"pair_frequency", "pair_recency"})
    assert {"pair_frequency", "pair_recency"} <= {m.name for m in S.methods_for("repeat_pair")}


# --- metrics (hand-calculated) ------------------------------------------------------------------------------


def test_average_precision_and_top_k_by_hand():
    # ranks: 1 pos, 2 neg, 3 pos, 4 neg -> AP = (1/1 + 2/3) / 2
    rows = [(0.9, 0, True), (0.8, 0, False), (0.7, 0, True), (0.1, 0, False)]
    m = rank_metrics(rows, k_max=2)
    assert math.isclose(m["average_precision"], (1 + 2 / 3) / 2)
    assert m["precision_at_k"] == 0.5 and m["recall_at_k"] == 0.5 and m["k"] == 2
    assert math.isclose(m["roc_auc"], 0.75)


def test_ties_use_the_shared_hash_and_auc_counts_ties_half():
    rows = [(1.0, 2, True), (1.0, 1, False)]  # tied score: the lower hash (negative) ranks first
    m = rank_metrics(rows)
    assert math.isclose(m["average_precision"], 0.5) and m["roc_auc"] == 0.5 and m["tie_rate"] == 1.0


@pytest.mark.parametrize("rows,ap,auc", [([], None, None), ([(1.0, 0, False)], None, None),
                                         ([(1.0, 0, True)], 1.0, None)])
def test_empty_no_positive_and_no_negative_cases_are_not_evaluable(rows, ap, auc):
    m = rank_metrics(rows)
    assert m["average_precision"] == ap and m["roc_auc"] == auc


def test_tiebreak_is_deterministic_and_label_free():
    assert tiebreak((1, 2)) == tiebreak((1, 2)) != tiebreak((1, 3))


# --- one synthetic new-pair forecast end to end ----------------------------------------------------------


def test_synthetic_new_pair_forecast_end_to_end():
    ev = triadic_stream(seed=11, nodes=80, events=4_000)
    b = boundaries(ev)
    hist = history(ev, b[6])
    lab = horizon_labels(ev, hist, b[7])
    horizon = b[7] - b[6]
    results = {m.name: evaluate(m, hist, lab, "new_pair", horizon) for m in S.methods_for("new_pair")}
    assert all(r.status == "completed" for r in results.values())
    assert len({r.candidates for r in results.values()}) == 1  # identical universe for every method
    prevalence = results["random"].prevalence
    assert results["resource_allocation"].average_precision > 2 * prevalence  # triadic signal is recovered
    assert results["constant"].tie_rate == 1.0
