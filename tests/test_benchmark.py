"""Development benchmark: coverage, stability, answer-key isolation, and split separation."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import networkx as nx
import pytest
from pydantic import ValidationError

from blackgrid.benchmark import (
    SPLITS,
    DevCase,
    TaskType,
    dev_cases,
    public_registry,
    seed_allowed,
    split_of,
)
from blackgrid.collegemsg import graph_sha256
from blackgrid.contracts import EdgeRemovalSensitivity, EdgeStatus, ExperimentSpec

REGISTRY = Path(__file__).resolve().parents[1] / "benchmarks" / "dev" / "registry.json"

# Pinned for the locked NetworkX version. A change means a generator's output moved.
GOLDEN = {
    "dev-001": "2757fa51c2dda4dd3d903957bcbe84a402c26f9deb0c58b26d5c81f4c06db758",
    "dev-002": "f72768785b495995b013ddbf0e28e074e4ba1df6c35c91ae59f3921decc66f33",
    "dev-003": "786bd71d6469192ae3b28a0ead46a3c771d9f92723920f1d9cb511d66e2aa4b4",
    "dev-004": "87f010ea6ee1463b44ba094ace2c5326dcb3cb080cb54b41fc4171807677d459",
    "dev-005": "44901d2501cf4965ac796392f1c9e23d41599365c3691edc91f58d6fe80c9abe",
    "dev-006": "72f7818b64043c5116b596fac0f10a3006ccbe42f82210e06afe59d13dd9ace3",
    "dev-007": "2922eadd0b76eae1575b7d754c8ef0a620bb89b91c3304e90f28e89673fb16fc",
    "dev-008": "350d0b17006ac94b2a7a85a9bf640bca51d814dbc77fe5514eaffa26743dc37b",
}

# Words that would reveal a generator family, latent labels, or the expected answer.
LEAK_TERMS = ("sbm", "planted", "erdos", "renyi", "heterogeneous", "disconnected_sparse", "p_in", "p_out",
              "label", "hidden", "verdict", "acceptable", "rationale", "block", "generator\"")


@pytest.fixture(scope="module")
def cases() -> dict[str, DevCase]:
    return dev_cases()


def test_coverage_eight_cases_four_families_four_tasks(cases):
    assert sorted(cases) == [f"dev-00{i}" for i in range(1, 9)]
    families = {c.truth.generator.family for c in cases.values()}
    assert families == {"planted_sbm", "erdos_renyi", "degree_heterogeneous", "disconnected_sparse"}
    assert {c.public.task_type for c in cases.values()} == set(TaskType)


def test_required_case_kinds_present(cases):
    assert any(c.truth.generator.family == "erdos_renyi" for c in cases.values())  # null
    assert any(nx.number_connected_components(c.graph) > 1 for c in cases.values())  # disconnected
    assert any(c.record.edge_status_counts.get(EdgeStatus.UNKNOWN, 0) > 0 for c in cases.values())  # missing
    assert any(c.public.task_type is TaskType.REFUSE_INVALID for c in cases.values())  # invalid request


def test_hashes_pinned_and_regeneration_identical(cases):
    again = dev_cases()
    for cid, case in cases.items():
        assert case.record.projection_sha256 == GOLDEN[cid] == graph_sha256(again[cid].graph), cid


def test_planner_view_contains_no_answer_key(cases):
    for cid, case in cases.items():
        public, graph, record = case.planner_view()
        text = (public.model_dump_json() + record.model_dump_json()).lower()
        for term in LEAK_TERMS:
            assert term not in text, f"{cid} leaks {term!r}"
        assert not graph.graph and not any(graph.nodes[n] for n in graph)
        assert not any(d for _, _, d in graph.edges(data=True))


def test_committed_registry_is_current_and_answer_free():
    on_disk = json.loads(REGISTRY.read_text(encoding="utf-8"))
    assert on_disk == json.loads(json.dumps(public_registry()))
    text = REGISTRY.read_text(encoding="utf-8").lower()
    for term in LEAK_TERMS:
        assert term not in text, term


def test_split_ids_and_seed_ranges_are_disjoint(cases):
    for cid, case in cases.items():
        assert split_of(cid) == "dev"
        assert seed_allowed(cid, case.truth.generator.seed)
    ranges = [set(r) for _, r in SPLITS.values()]
    assert all(not (a & b) for i, a in enumerate(ranges) for b in ranges[i + 1:])
    assert split_of("test-001") == "test" and not seed_allowed("test-001", 11)
    with pytest.raises(ValueError):
        split_of("sbm-1")


# --- case-specific properties the evaluator relies on -------------------------------------------


def test_missing_edge_case_hides_true_edges_in_unknown_pairs(cases):
    case = cases["dev-006"]
    hidden = case.truth.hidden_edges
    assert hidden and not any(case.graph.has_edge(u, v) for u, v in hidden)
    full = case.graph.copy()
    full.add_edges_from(hidden)
    # The observation mask, not the true network, creates the apparent fragmentation.
    assert nx.number_connected_components(case.graph) > nx.number_connected_components(full) == 1


def test_disconnected_case_has_one_component_per_piece(cases):
    case = cases["dev-005"]
    assert nx.number_connected_components(case.graph) == case.truth.generator.params["components"]


def test_degree_case_is_connected_and_heterogeneous(cases):
    graph = cases["dev-003"].graph
    degrees = [d for _, d in graph.degree()]
    assert nx.is_connected(graph)
    assert max(degrees) >= 5 * statistics.median(degrees)


def test_invalid_method_request_cannot_become_an_experiment(cases):
    request = cases["dev-007"].public.request
    with pytest.raises(ValidationError):
        ExperimentSpec(
            experiment_id="x", graph_id="dev-007", status="exploratory", hypothesis="h",
            competing_explanations=("c",), task="community_structure_vs_null", method=request["method"],
            statistic="modularity", null_model="degree_preserving_double_edge_swap", null_replicates=99, seed=1,
            sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=0.1, replicates=10),
        )
