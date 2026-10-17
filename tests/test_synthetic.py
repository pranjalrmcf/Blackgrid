"""Synthetic fixtures are seeded, stable, and keep truth out of the analyzable record."""

from __future__ import annotations

from blackgrid.collegemsg import graph_sha256
from blackgrid.contracts import DataOrigin, canonical_sha256
from blackgrid.synthetic import erdos_renyi, planted_sbm, tiny_fixtures

# Pinned for the locked NetworkX version (uv.lock). A change means the generator output moved.
GOLDEN = {
    "dev-001": "2757fa51c2dda4dd3d903957bcbe84a402c26f9deb0c58b26d5c81f4c06db758",
    "dev-002": "f72768785b495995b013ddbf0e28e074e4ba1df6c35c91ae59f3921decc66f33",
}


def test_same_seed_same_graph_different_seed_different_graph():
    a, _ = planted_sbm("x", blocks=3, block_size=10, p_in=0.6, p_out=0.03, seed=1)
    b, _ = planted_sbm("x", blocks=3, block_size=10, p_in=0.6, p_out=0.03, seed=1)
    c, _ = planted_sbm("x", blocks=3, block_size=10, p_in=0.6, p_out=0.03, seed=2)
    assert graph_sha256(a.graph) == graph_sha256(b.graph) != graph_sha256(c.graph)


def test_fixture_hashes_are_pinned():
    for name, (graph, _) in tiny_fixtures().items():
        assert graph.record.projection_sha256 == GOLDEN[name], name


def test_truth_is_separate_from_analyzable_record():
    (graph, truth) = tiny_fixtures()["dev-001"]
    dumped = graph.record.model_dump_json()
    for leak in ("planted", "label", "sbm", "p_in", "p_out", "blocks"):
        assert leak not in dumped, leak  # neither labels nor the generator family/params
    assert graph.record.origin is DataOrigin.SYNTHETIC
    assert graph.record.generator_sha256 == canonical_sha256(truth.generator)
    assert set(truth.planted_labels) == set(graph.graph.nodes())
    assert sorted(set(truth.planted_labels.values())) == [0, 1, 2]
    g = graph.graph
    assert not g.graph, "graph-level attributes (e.g. SBM 'partition') must be stripped"
    assert not any(g.nodes[n] for n in g.nodes()), "node attributes (e.g. SBM 'block') must be stripped"
    assert not any(d for _, _, d in g.edges(data=True))


def test_er_fixture_has_exact_edge_count_and_no_labels():
    graph, truth = erdos_renyi("er", n=30, m=60, seed=3)
    assert graph.graph.number_of_edges() == 60 == graph.record.unique_edges
    assert truth.planted_labels is None
