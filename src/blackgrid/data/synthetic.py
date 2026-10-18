"""Seeded synthetic graphs with evaluator-only truth.

`generate` returns the analyzable graph and its GraphRecord separately from `EvaluatorTruth`.
Planner, critic, and report code must only ever receive the first two; truth goes to the
evaluator. Hashes are stable for a given seed and the locked NetworkX version.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import networkx as nx

from blackgrid.data.collegemsg import graph_sha256
from blackgrid.contracts import (
    Contract,
    DataOrigin,
    EdgeStatus,
    GeneratorSpec,
    GraphRecord,
    canonical_sha256,
)

GENERATOR_VERSION = "synthetic-v0.1"


class EvaluatorTruth(Contract):
    """Generator latent structure. Evaluator-only; never passed to planner, critic, or report."""

    graph_id: str
    generator: GeneratorSpec
    planted_labels: dict[int, int] | None = None
    hidden_edges: tuple[tuple[int, int], ...] = ()  # true edges inside unobserved pairs
    note: str


@dataclass(frozen=True)
class SyntheticGraph:
    record: GraphRecord
    graph: nx.Graph


def planted_sbm(graph_id: str, *, blocks: int, block_size: int, p_in: float, p_out: float, seed: int
                ) -> tuple[SyntheticGraph, EvaluatorTruth]:
    sizes = [block_size] * blocks
    probs = [[p_in if i == j else p_out for j in range(blocks)] for i in range(blocks)]
    graph = _bare(nx.stochastic_block_model(sizes, probs, seed=seed))
    labels = {node: node // block_size for node in graph.nodes()}
    spec = GeneratorSpec(
        family="planted_sbm",
        params={"blocks": blocks, "block_size": block_size, "p_in": p_in, "p_out": p_out},
        seed=seed,
        version=GENERATOR_VERSION,
    )
    truth = EvaluatorTruth(
        graph_id=graph_id,
        generator=spec,
        planted_labels=labels,
        note="Planted blocks are generator labels; a modularity optimum need not coincide with them.",
    )
    return _wrap(graph_id, graph, spec), truth


def erdos_renyi(graph_id: str, *, n: int, m: int, seed: int) -> tuple[SyntheticGraph, EvaluatorTruth]:
    graph = _bare(nx.gnm_random_graph(n, m, seed=seed))
    spec = GeneratorSpec(family="erdos_renyi", params={"n": n, "m": m}, seed=seed, version=GENERATOR_VERSION)
    truth = EvaluatorTruth(
        graph_id=graph_id,
        generator=spec,
        planted_labels=None,
        note="No planted communities; nonzero modularity here arises from random fluctuations.",
    )
    return _wrap(graph_id, graph, spec), truth


def degree_heterogeneous(graph_id: str, *, n: int, max_weight: float, exponent: float, min_weight: float,
                         seed: int) -> tuple[SyntheticGraph, EvaluatorTruth]:
    """Chung-Lu graph with heavy-tailed expected degrees and no planted groups.

    Restricted to its largest connected component (relabelled 0..k-1) so the case isolates the
    degree confound from disconnection, which dev-005 covers separately.
    """
    weights = [max(min_weight, max_weight * (i + 1) ** -exponent) for i in range(n)]
    generated = _bare(nx.expected_degree_graph(weights, seed=seed, selfloops=False))
    largest = generated.subgraph(max(nx.connected_components(generated), key=len))
    graph = _bare(nx.convert_node_labels_to_integers(largest, ordering="sorted"))
    spec = GeneratorSpec(
        family="degree_heterogeneous",
        params={"n": n, "max_weight": max_weight, "exponent": exponent, "min_weight": min_weight,
                "largest_component_only": 1},
        seed=seed,
        version=GENERATOR_VERSION,
    )
    truth = EvaluatorTruth(
        graph_id=graph_id,
        generator=spec,
        note="No planted groups; any modularity beyond an Erdos-Renyi null is explained by degree heterogeneity.",
    )
    return _wrap(graph_id, graph, spec), truth


def disconnected_sparse(graph_id: str, *, components: int, size: int, edges_per: int, seed: int
                        ) -> tuple[SyntheticGraph, EvaluatorTruth]:
    """Disjoint random pieces: modularity is high by construction, not by community signal."""
    pieces = [nx.gnm_random_graph(size, edges_per, seed=seed + i) for i in range(components)]
    graph = _bare(nx.disjoint_union_all(pieces))
    labels = {node: node // size for node in graph.nodes()}
    spec = GeneratorSpec(
        family="disconnected_sparse",
        params={"components": components, "size": size, "edges_per": edges_per},
        seed=seed,
        version=GENERATOR_VERSION,
    )
    truth = EvaluatorTruth(
        graph_id=graph_id,
        generator=spec,
        planted_labels=labels,
        note="Pieces are disconnected; a degree-preserving null that swaps within pieces differs from one that mixes them.",
    )
    return _wrap(graph_id, graph, spec), truth


def masked_sbm(graph_id: str, *, blocks: int, block_size: int, p_in: float, p_out: float,
               unobserved_fraction: float, seed: int) -> tuple[SyntheticGraph, EvaluatorTruth]:
    """Planted SBM observed through a mask: a fraction of node pairs is never observed.

    Pairs in the mask are UNKNOWN, not non-links. True edges inside them are evaluator-only.
    """
    full = _bare(nx.stochastic_block_model([block_size] * blocks,
                                           [[p_in if i == j else p_out for j in range(blocks)] for i in range(blocks)],
                                           seed=seed))
    pairs = sorted((u, v) for u in full.nodes() for v in full.nodes() if u < v)
    masked = set(random.Random(seed).sample(pairs, round(unobserved_fraction * len(pairs))))
    observed = nx.Graph()
    observed.add_nodes_from(full.nodes())
    observed.add_edges_from(e for e in full.edges() if (min(e), max(e)) not in masked)
    hidden = tuple(sorted((min(e), max(e)) for e in full.edges() if (min(e), max(e)) in masked))
    spec = GeneratorSpec(
        family="planted_sbm",
        params={"blocks": blocks, "block_size": block_size, "p_in": p_in, "p_out": p_out,
                "unobserved_fraction": unobserved_fraction},
        seed=seed,
        version=GENERATOR_VERSION,
    )
    truth = EvaluatorTruth(
        graph_id=graph_id,
        generator=spec,
        planted_labels={node: node // block_size for node in full.nodes()},
        hidden_edges=hidden,
        note="Observed fragmentation, if any, comes from the observation mask, not from the true network.",
    )
    return _wrap(graph_id, observed, spec, unknown_pairs=len(masked)), truth


def _bare(generated: nx.Graph) -> nx.Graph:
    """Copy only nodes and edges. Generators attach truth as attributes (SBM sets node 'block'
    and graph 'partition'); those must never reach analysis code."""
    graph = nx.Graph()
    graph.add_nodes_from(sorted(generated.nodes()))
    graph.add_edges_from(generated.edges())
    return graph


def _wrap(graph_id: str, graph: nx.Graph, spec: GeneratorSpec, *, unknown_pairs: int = 0) -> SyntheticGraph:
    edges = graph.number_of_edges()
    statuses = {EdgeStatus.OBSERVED: edges}
    if unknown_pairs:
        statuses[EdgeStatus.UNKNOWN] = unknown_pairs
    record = GraphRecord(
        graph_id=graph_id,
        origin=DataOrigin.SYNTHETIC,
        generator_sha256=canonical_sha256(spec),
        raw_events=edges,
        window_events=edges,
        self_loop_events_excluded=0,
        exact_duplicate_rows_flagged=0,
        active_nodes=graph.number_of_nodes(),
        unique_edges=edges,
        edge_status_counts=statuses,
        projection_sha256=graph_sha256(graph),
    )
    return SyntheticGraph(record=record, graph=graph)


def tiny_fixtures() -> dict[str, tuple[SyntheticGraph, EvaluatorTruth]]:
    """Day 3 seeded fixtures; Day 4 expands these to the full development set.

    IDs are neutral on purpose: a name like "sbm" would reveal the answer to the planner.
    dev-001 is a planted 3-block SBM; dev-002 is an Erdos-Renyi null (evaluator knowledge only).
    """
    return {
        "dev-001": planted_sbm("dev-001", blocks=3, block_size=10, p_in=0.6, p_out=0.03, seed=11),
        "dev-002": erdos_renyi("dev-002", n=30, m=60, seed=12),
    }
