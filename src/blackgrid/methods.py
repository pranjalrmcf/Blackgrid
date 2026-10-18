"""Exploratory CPU method comparison; never changes the historical optimizer.

Shared null graphs, validated partitions, one score implementation, bounded scopes.
No generator truth is used for fitting, scoring or selecting a partition.
"""
from __future__ import annotations

import math
import random
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from importlib.metadata import version
from typing import Literal

import networkx as nx

from blackgrid.collegemsg import graph_sha256
from blackgrid.contracts import Contract
from blackgrid.experiment import DeadlineExceeded, derive_seed, double_edge_swap

ADAPTER_VERSION = "methods-v1"


class MethodSpec(Contract):
    null_replicates: Literal[99] = 99
    restarts: Literal[5] = 5
    leiden_iterations: Literal[2] = 2
    seeds: tuple[Literal[31], Literal[47], Literal[83]] = (31, 47, 83)
    timeout_s: Literal[60] = 60


def backend_versions() -> dict:
    return {name: version(name) for name in ("networkx", "igraph", "leidenalg")}


def validate_partition(graph: nx.Graph, parts: list[set]) -> int:
    """Reject omissions/overlap/foreign nodes; report disconnected communities."""
    if not parts or any(not p for p in parts):
        raise ValueError("partition has empty communities")
    flattened = [n for part in parts for n in part]
    if len(flattened) != len(set(flattened)) or set(flattened) != set(graph):
        raise ValueError("partition must cover every node exactly once")
    return sum(not nx.is_connected(graph.subgraph(part)) for part in parts)


@dataclass(frozen=True)
class Partition:
    parts: list[set]
    q: float
    disconnected: int


def optimize(graph: nx.Graph, method: str, master: int, *labels: object, restarts: int = 5,
             deadline: float = math.inf) -> Partition:
    if method not in ("louvain", "leiden"):
        raise ValueError("unknown optimizer")
    if graph.is_directed() or graph.is_multigraph() or nx.number_of_selfloops(graph):
        raise ValueError("requires a simple undirected loop-free graph")
    if not graph.number_of_edges() or restarts < 1:
        raise ValueError("requires edges and at least one restart")
    if len(graph) > 1000 or graph.number_of_edges() > 10000:
        raise ValueError("graph exceeds experimental caps")
    converted = None
    nodes = list(graph)
    if method == "leiden":
        import igraph as ig
        import leidenalg as la

        indices = {node: i for i, node in enumerate(nodes)}
        converted = ig.Graph(n=len(nodes), edges=[(indices[u], indices[v]) for u, v in graph.edges()],
                             directed=False)
    best = None
    for restart in range(restarts):
        if time.perf_counter() > deadline:
            raise DeadlineExceeded("method scope exceeded 60-second deadline")
        seed = derive_seed(master, *labels, method, restart) % (2**31 - 1)
        if method == "louvain":
            parts = nx.community.louvain_communities(graph, resolution=1, seed=seed)
        else:
            found = la.find_partition(converted, la.RBConfigurationVertexPartition,
                                      resolution_parameter=1, n_iterations=2, seed=seed)
            parts = [{nodes[index] for index in group} for group in found]
        disconnected = validate_partition(graph, parts)
        q = nx.community.modularity(graph, parts, resolution=1)
        if best is None or q > best.q:
            best = Partition(parts, q, disconnected)
    if time.perf_counter() > deadline:
        raise DeadlineExceeded("method scope exceeded deadline")
    return best


def variation_information(a: list[set], b: list[set]) -> float:
    """Partition variation of information in natural-log units, invariant to labels."""
    if set().union(*a) != set().union(*b):
        raise ValueError("partitions must have the same universe")
    n = sum(map(len, a))
    entropy = lambda p: -sum(len(s) / n * math.log(len(s) / n) for s in p)
    mutual = sum(len(x & y) / n * math.log(n * len(x & y) / (len(x) * len(y)))
                 for x in a for y in b if x & y)
    return max(0., entropy(a) + entropy(b) - 2 * mutual)


def compare_scope(graph: nx.Graph, master: int, scope: str, spec: MethodSpec) -> dict:
    start = time.perf_counter()
    deadline = start + spec.timeout_s
    if graph.number_of_edges() < 20 or len(graph) - nx.number_of_isolates(graph) < 10:
        return {"status": "abstained", "reason": "S1/S2: insufficient edges or nonisolated nodes"}
    original_hash = graph_sha256(graph)
    observed, times = {}, Counter()
    for method in ("louvain", "leiden"):
        before = time.perf_counter()
        observed[method] = optimize(graph, method, master, scope, "observed", deadline=deadline)
        times[method] += time.perf_counter() - before
    values = {m: [] for m in observed}
    hashes, swaps_log = [], []
    failed = identical = 0
    target = 10 * graph.number_of_edges()
    for r in range(spec.null_replicates):
        if time.perf_counter() > deadline:
            raise DeadlineExceeded("method scope exceeded deadline")
        null, swaps = double_edge_swap(graph, target, 100 * target,
                                       random.Random(derive_seed(master, scope, "shared-null", r)))
        swaps_log.append(swaps.model_dump(mode="json"))
        if not swaps.reached_target:
            failed += 1
            continue
        digest = graph_sha256(null)
        identical += digest == original_hash
        hashes.append(digest)
        for method in observed:
            before = time.perf_counter()
            part = optimize(null, method, master, scope, "null", r, deadline=deadline)
            times[method] += time.perf_counter() - before
            values[method].append(part.q)
    count = len(hashes)
    suitable = count > 0 and failed <= .05 * spec.null_replicates and count - identical >= .95 * count
    methods = {}
    for method, found in observed.items():
        qvalues = values[method]
        exceed = sum(q >= found.q for q in qvalues)
        methods[method] = {"q": found.q, "null_values": qvalues,
                           "null_mean": statistics.fmean(qvalues) if count else None,
                           "delta_q": found.q - statistics.fmean(qvalues) if count else None,
                           "exceedances": exceed, "p_value": (1 + exceed) / (1 + count) if suitable else None,
                           "p_resolution": 1 / (1 + count) if count else None,
                           "communities": len(found.parts), "disconnected_communities": found.disconnected,
                           "partition": [sorted(p) for p in found.parts], "optimizer_elapsed_s": times[method]}
    return {"status": "completed" if suitable else "abstained", "nodes": len(graph),
            "edges": graph.number_of_edges(), "projection_sha256": original_hash,
            "failed_nulls": failed, "identical_nulls": identical, "null_hashes": hashes,
            "swap_log": swaps_log, "methods": methods, "elapsed_s": time.perf_counter() - start,
            "reason": None if suitable else "S3/S4: unsuitable null randomization"}


def comparison_verdict(primary: dict, secondary: dict | None, connected: bool, method: str,
                       unknown_pairs: int = 0) -> str:
    if primary["status"] != "completed":
        return "abstain"
    if primary["methods"][method]["p_value"] > .05:
        return "not_supported"
    if not connected and (not secondary or secondary["status"] != "completed" or
                          secondary["methods"][method]["p_value"] > .05):
        return "inconclusive"
    return "inconclusive" if unknown_pairs else "supported"
