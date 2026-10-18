"""Trusted structural tools. Node rows are local artifacts, never model evidence."""
from __future__ import annotations

import math
import hashlib
import json
import random
import time
from typing import Literal

import networkx as nx
from pydantic import Field

from blackgrid.contracts import Contract
from blackgrid.experiment import DeadlineExceeded

STRUCTURAL_VERSION = "structural-v1"


class StructuralSpec(Contract):
    version: Literal["structural-v1"] = STRUCTURAL_VERSION
    family: Literal["centrality", "bridge", "clarify"]
    graph_sha256: str
    seed: int
    top_k: Literal[5] = 5
    boundary_ties_included: Literal[True] = True
    exact_betweenness_max_nodes: Literal[200] = 200
    sampled_sources: Literal[128] = 128
    resolution: Literal[1] = 1
    partition_restarts: Literal[5] = 5
    sensitivity_replicates: Literal[3] = 3
    removal_fraction: Literal[0.1] = .1
    max_tool_calls: Literal[6] = 6
    max_follow_up_rounds: Literal[1] = 1
    evidence_level: Literal["descriptive"] = "descriptive"


def partition_hash(rows: list) -> str:
    return hashlib.sha256(json.dumps([r.model_dump() for r in rows], sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class NodeRow(Contract):
    node: str
    degree: int = Field(ge=0)
    betweenness: float = Field(default=0, ge=0)  # sampled estimates may exceed one; never clip them
    degree_rank: int = Field(default=1, ge=1)
    betweenness_rank: int = Field(default=1, ge=1)
    community: int = Field(default=0, ge=0)
    cross_degree: int = Field(default=0, ge=0)
    cross_fraction: float = Field(default=0, ge=0, le=1)
    bridge_rank: int = Field(default=1, ge=1)


class StructuralResult(Contract):
    version: Literal["structural-v1"] = STRUCTURAL_VERSION
    tool: Literal["node_centrality", "community_partition", "community_bridge", "ranking_sensitivity"]
    graph_sha256: str
    nodes: int = Field(ge=0)
    edges: int = Field(ge=0)
    seed: int
    summary: dict[str, int | float | str | bool | None]
    rows: tuple[NodeRow, ...] = ()


def check_time(deadline: float) -> None:
    if time.perf_counter() > deadline:
        raise DeadlineExceeded("structural tool exceeded its cooperative deadline")


def ordered(graph: nx.Graph) -> list:
    nodes = sorted(graph, key=lambda n: (type(n).__name__, str(n)))
    if len({str(n) for n in nodes}) != len(nodes):
        raise ValueError("node references are ambiguous after string conversion")
    return nodes


def ranks(values: dict) -> dict:
    """Competition ranks; exact numerical ties share rank."""
    return {n: 1 + sum(v > x for v in values.values()) for n, x in values.items()}


def centrality(graph: nx.Graph, seed: int, deadline: float) -> tuple[list[NodeRow], dict]:
    nodes = ordered(graph)
    # Per-source checks bound cooperative work; each source remains trusted NetworkX code.
    sources = nodes if len(nodes) <= 200 else random.Random(seed).sample(nodes, 128)
    between = dict.fromkeys(nodes, 0.0)
    for source in sources:
        check_time(deadline)
        scores = nx.betweenness_centrality_subset(graph, [source], nodes, normalized=True)
        for n in nodes:
            between[n] += scores[n]
    factor = len(nodes) / len(sources) if sources else 1
    between = {n: max(0.0, x * factor) for n, x in between.items()}
    degree = dict(graph.degree())
    dr, br = ranks(degree), ranks(between)
    rows = [NodeRow(node=str(n), degree=degree[n], betweenness=between[n],
                    degree_rank=dr[n], betweenness_rank=br[n]) for n in nodes]
    return rows, {"metric": "degree_and_betweenness", "normalization": "global_n_unreachable_zero",
                  "approximate": len(nodes) > 200, "sample_sources": len(sources),
                  "max_degree": max(degree.values(), default=0),
                  "max_betweenness": max(between.values(), default=0.0)}


def partition(graph: nx.Graph, seed: int, deadline: float) -> tuple[list[NodeRow], dict]:
    nodes = ordered(graph)
    if not graph.number_of_edges():
        groups = [{n} for n in nodes]
    else:
        best, groups = -math.inf, []
        for restart in range(5):
            check_time(deadline)
            candidate = nx.community.louvain_communities(graph, resolution=1, seed=seed + restart)
            q = nx.community.modularity(graph, candidate, resolution=1)
            if q > best:
                best, groups = q, candidate
    position = {n: i for i, n in enumerate(nodes)}
    groups = sorted(groups, key=lambda g: min(position[n] for n in g))
    membership = {n: i for i, group in enumerate(groups) for n in group}
    rows = [NodeRow(node=str(n), degree=graph.degree(n), community=membership[n]) for n in nodes]
    return rows, {"method": "louvain", "resolution": 1, "restarts": 5,
                  "communities": len(groups), "partition_sha256": partition_hash(rows),
                  "interpretation": "descriptive_partition_not_statistical_support"}


def bridges(graph: nx.Graph, partition_rows: list[NodeRow]) -> tuple[list[NodeRow], dict]:
    nodes = ordered(graph)
    group = {row.node: row.community for row in partition_rows}
    if set(group) != {str(n) for n in nodes}:
        raise ValueError("partition must cover exactly the graph nodes")
    cross = {n: sum(group[str(n)] != group[str(v)] for v in graph[n]) for n in nodes}
    rank = ranks(cross)
    rows = [NodeRow(node=str(n), degree=graph.degree(n), community=group[str(n)], cross_degree=cross[n],
                    cross_fraction=cross[n] / graph.degree(n) if graph.degree(n) else 0,
                    bridge_rank=rank[n]) for n in nodes]
    return rows, {"metric": "cross_community_degree", "max_cross_degree": max(cross.values(), default=0),
                  "partition_sha256": partition_hash(partition_rows),
                  "interpretation": "partition_dependent_not_causal_influence"}


def top_set(values: dict, k: int = 5) -> set:
    ranked = ranks(values)
    return {n for n, rank in ranked.items() if rank <= k}


def spearman(a: dict, b: dict) -> float | None:
    def average(values):
        return {n: 1 + sum(v > x for v in values.values()) + (sum(v == x for v in values.values()) - 1) / 2
                for n, x in values.items()}
    ar, br = average(a), average(b)
    if not ar:
        return None
    am, bm = sum(ar.values()) / len(ar), sum(br.values()) / len(br)
    numerator = sum((ar[n] - am) * (br[n] - bm) for n in ar)
    denominator = math.sqrt(sum((x - am)**2 for x in ar.values()) * sum((x - bm)**2 for x in br.values()))
    return numerator / denominator if denominator else None


def compute(name: str, graph: nx.Graph, graph_sha: str, seed: int, seconds: float,
            previous: dict[str, dict]) -> dict:
    if graph.is_directed() or graph.is_multigraph() or nx.number_of_selfloops(graph):
        raise ValueError("structural tools require a simple undirected graph without self loops")
    deadline = time.perf_counter() + seconds
    if name == "node_centrality":
        rows, summary = centrality(graph, seed, deadline)
    elif name == "community_partition":
        rows, summary = partition(graph, seed, deadline)
    elif name == "community_bridge":
        saved = StructuralResult.model_validate(previous["community_partition.json"])
        rows, summary = bridges(graph, list(saved.rows))
    elif name == "ranking_sensitivity":
        bridge = "community_bridge.json" in previous
        saved = StructuralResult.model_validate(previous["community_bridge.json" if bridge else "node_centrality.json"])
        metric = "cross_degree" if bridge else "betweenness"
        base = {r.node: getattr(r, metric) for r in saved.rows}
        overlaps, correlations = [], []
        edges = sorted(graph.edges(), key=lambda e: tuple(sorted(map(str, e))))
        removed = math.floor(.1 * len(edges))
        for i in range(3):
            check_time(deadline)
            reduced = graph.copy()
            reduced.remove_edges_from(random.Random(seed + 10000 + i).sample(edges, removed))
            if bridge:
                part, _ = partition(reduced, seed, deadline)
                rr, _ = bridges(reduced, part)
            else:
                rr, _ = centrality(reduced, seed, deadline)
            scores = {r.node: getattr(r, metric) for r in rr}
            aa, bb = top_set(base), top_set(scores)
            overlaps.append(len(aa & bb) / len(aa | bb) if aa | bb else 1.0)
            rho = spearman(base, scores)
            if rho is not None:
                correlations.append(rho)
        rows = []
        summary = {"metric": metric, "mechanism": "uniform", "removal_fraction": .1,
                   "replicates": 3, "removed_edges_per_replicate": removed, "removed_pair_status": "unknown",
                   "top_k": 5, "boundary_ties_included": True, "mean_top_jaccard": sum(overlaps) / 3,
                   "mean_spearman": sum(correlations) / len(correlations) if correlations else None,
                   "defined_correlations": len(correlations), "interpretation": "sensitivity_not_uncertainty_interval"}
    else:
        raise ValueError("unknown structural tool")
    check_time(deadline)
    return StructuralResult(tool=name, graph_sha256=graph_sha, nodes=len(graph), edges=graph.number_of_edges(),
                            seed=seed, summary=summary, rows=tuple(rows)).model_dump(mode="json")
