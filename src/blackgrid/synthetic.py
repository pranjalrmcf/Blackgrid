"""Seeded synthetic graphs with evaluator-only truth.

`generate` returns the analyzable graph and its GraphRecord separately from `EvaluatorTruth`.
Planner, critic, and report code must only ever receive the first two; truth goes to the
evaluator. Hashes are stable for a given seed and the locked NetworkX version.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from blackgrid.collegemsg import graph_sha256
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


def _bare(generated: nx.Graph) -> nx.Graph:
    """Copy only nodes and edges. Generators attach truth as attributes (SBM sets node 'block'
    and graph 'partition'); those must never reach analysis code."""
    graph = nx.Graph()
    graph.add_nodes_from(sorted(generated.nodes()))
    graph.add_edges_from(generated.edges())
    return graph


def _wrap(graph_id: str, graph: nx.Graph, spec: GeneratorSpec) -> SyntheticGraph:
    edges = graph.number_of_edges()
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
        edge_status_counts={EdgeStatus.OBSERVED: edges},
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
