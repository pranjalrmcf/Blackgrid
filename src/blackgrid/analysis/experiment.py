"""Graph profiling and the single Sprint 1 experiment (protocols/sprint01_experiment.md, exp-v1).

Modularity of the best Louvain partition (best of k restarts) on the observed graph is compared
with the same procedure applied to degree-preserving double-edge-swap randomizations. All
randomness flows from derived seeds, so a spec plus a graph reproduces the result exactly.
"""

from __future__ import annotations

import hashlib
import random
import statistics
import time
from typing import Literal

import networkx as nx
from pydantic import Field

from blackgrid.data.collegemsg import graph_sha256
from blackgrid.contracts import (
    Contract,
    ExperimentResult,
    ExperimentSpec,
    NonEmpty,
    NullSummary,
    Outcome,
)

Verdict = Literal["supported", "not_supported", "inconclusive", "abstain"]


class DeadlineExceeded(RuntimeError):
    """The experiment ran past its tool timeout."""


# --- Seeds --------------------------------------------------------------------------------------


def derive_seed(master: int, *labels: object) -> int:
    """Deterministic child seed: sha256(master|label|...) mod 2**32."""
    text = "|".join([str(master), *map(str, labels)])
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:4], "big")


# --- Profiling ----------------------------------------------------------------------------------


class GraphProfile(Contract):
    nodes: int
    edges: int
    isolated_nodes: int
    components: int
    largest_component_nodes: int
    largest_component_edges: int
    density: float
    degree_min: int
    degree_median: float
    degree_mean: float
    degree_max: int
    transitivity: float


def profile(graph: nx.Graph) -> GraphProfile:
    degrees = [d for _, d in graph.degree()] or [0]
    components = list(nx.connected_components(graph)) if graph.number_of_nodes() else []
    largest = max(components, key=len) if components else set()
    return GraphProfile(
        nodes=graph.number_of_nodes(),
        edges=graph.number_of_edges(),
        isolated_nodes=nx.number_of_isolates(graph),
        components=len(components),
        largest_component_nodes=len(largest),
        largest_component_edges=graph.subgraph(largest).number_of_edges(),
        density=round(nx.density(graph), 12) if graph.number_of_nodes() > 1 else 0.0,
        degree_min=min(degrees),
        degree_median=float(statistics.median(degrees)),
        degree_mean=round(statistics.fmean(degrees), 12),
        degree_max=max(degrees),
        transitivity=round(nx.transitivity(graph), 12),
    )


# --- Modularity ---------------------------------------------------------------------------------


def modularity(graph: nx.Graph, communities: list[set]) -> float:
    """Newman-Girvan modularity, written out independently of NetworkX for oracle checks.

    Q = sum_c [ L_c / m - (D_c / 2m)^2 ], L_c = edges inside c, D_c = total degree of c.
    """
    m = graph.number_of_edges()
    if m == 0:
        raise ValueError("modularity is undefined for a graph with no edges")
    total = 0.0
    for community in communities:
        inside = graph.subgraph(community).number_of_edges()
        degree = sum(d for _, d in graph.degree(community))
        total += inside / m - (degree / (2 * m)) ** 2
    return total


def best_modularity(graph: nx.Graph, master: int, *labels: object, restarts: int) -> float:
    """Maximum Q over `restarts` Louvain runs with derived seeds (same effort for every graph)."""
    best = float("-inf")
    for k in range(restarts):
        seed = derive_seed(master, *labels, "louvain", k)
        parts = nx.community.louvain_communities(graph, resolution=1.0, seed=seed)
        best = max(best, nx.community.modularity(graph, parts, resolution=1.0))
    return best


# --- Null model ---------------------------------------------------------------------------------


class SwapOutcome(Contract):
    accepted: int
    attempts: int
    reached_target: bool


def double_edge_swap(graph: nx.Graph, target: int, max_attempts: int, rng: random.Random
                     ) -> tuple[nx.Graph, SwapOutcome]:
    """Degree-preserving rewiring of a simple graph by uniform edge-pair swaps.

    (a,b),(c,d) -> (a,d),(c,b) or (a,c),(b,d), each with probability 1/2; a swap creating a
    self-loop or duplicate edge is rejected. Degrees are preserved exactly by construction.
    """
    null = nx.Graph()
    null.add_nodes_from(graph.nodes())
    edges = [tuple(e) for e in graph.edges()]
    null.add_edges_from(edges)
    accepted = attempts = 0
    while accepted < target and attempts < max_attempts and len(edges) >= 2:
        attempts += 1
        i, j = rng.sample(range(len(edges)), 2)
        (a, b), (c, d) = edges[i], edges[j]
        if rng.random() < 0.5:
            new1, new2 = (a, d), (c, b)
        else:
            new1, new2 = (a, c), (b, d)
        if new1[0] == new1[1] or new2[0] == new2[1]:
            continue
        if null.has_edge(*new1) or null.has_edge(*new2):
            continue
        null.remove_edge(a, b)
        null.remove_edge(c, d)
        null.add_edge(*new1)
        null.add_edge(*new2)
        edges[i], edges[j] = new1, new2
        accepted += 1
    return null, SwapOutcome(accepted=accepted, attempts=attempts, reached_target=accepted >= target)


# --- One analysis (whole graph or largest component) --------------------------------------------


class Analysis(Contract):
    scope: Literal["whole_graph", "largest_component"]
    suitable: bool
    unsuitable_reasons: tuple[NonEmpty, ...] = ()
    result: ExperimentResult
    nodes: int
    edges: int
    null_failed: int = 0
    null_identical_to_observed: int = 0
    mean_swap_acceptance: float | None = None
    delta_q: float | None = None
    z: float | None = None
    null_values: tuple[float, ...] = ()  # every successful null Q, in replicate order (for plots/audit)


def _check_deadline(deadline: float) -> None:
    if time.perf_counter() > deadline:
        raise DeadlineExceeded("experiment exceeded its tool timeout")


def analyse(graph: nx.Graph, spec: ExperimentSpec, scope: str, deadline: float) -> Analysis:
    rule = spec.suitability
    eid = f"{spec.experiment_id}:{scope}"
    nonisolated = graph.number_of_nodes() - nx.number_of_isolates(graph)
    reasons = []
    if graph.number_of_edges() < rule.min_edges:
        reasons.append(f"S1: {graph.number_of_edges()} edges < {rule.min_edges}")
    if nonisolated < rule.min_nonisolated_nodes:
        reasons.append(f"S2: {nonisolated} non-isolated nodes < {rule.min_nonisolated_nodes}")
    sizes = dict(scope=scope, nodes=graph.number_of_nodes(), edges=graph.number_of_edges())
    if reasons:
        return Analysis(**sizes, suitable=False, unsuitable_reasons=tuple(reasons),
                        result=ExperimentResult(experiment_id=eid, outcome=Outcome.ABSTAINED, reason="; ".join(reasons)))

    master = spec.seed
    observed_q = best_modularity(graph, master, scope, "observed", restarts=spec.optimizer_restarts)
    observed_hash = graph_sha256(graph)
    target = round(spec.swaps_per_edge * graph.number_of_edges())
    null_q: list[float] = []
    failed = identical = 0
    acceptance: list[float] = []
    for r in range(spec.null_replicates):
        _check_deadline(deadline)
        rng = random.Random(derive_seed(master, scope, "null", r))
        null, swaps = double_edge_swap(graph, target, spec.swap_attempt_factor * target, rng)
        acceptance.append(swaps.accepted / swaps.attempts if swaps.attempts else 0.0)
        if not swaps.reached_target:
            failed += 1
            continue
        if graph_sha256(null) == observed_hash:
            identical += 1
        null_q.append(best_modularity(null, master, scope, "null", r, restarts=spec.optimizer_restarts))

    ok = len(null_q)
    if failed > rule.max_failed_null_fraction * spec.null_replicates:
        reasons.append(f"S3: {failed}/{spec.null_replicates} null replicates failed to reach {target} swaps")
    if ok and (ok - identical) < rule.min_distinct_null_fraction * ok:
        reasons.append(f"S4: only {ok - identical}/{ok} null graphs differ from the observed graph")
    if not ok:
        reasons.append("S3: no successful null replicates")
    diagnostics = dict(null_failed=failed, null_identical_to_observed=identical,
                       mean_swap_acceptance=round(statistics.fmean(acceptance), 12))
    if reasons:
        return Analysis(**sizes, **diagnostics, suitable=False, unsuitable_reasons=tuple(reasons),
                        result=ExperimentResult(experiment_id=eid, outcome=Outcome.ABSTAINED, reason="; ".join(reasons)))

    exceed = sum(q >= observed_q for q in null_q)
    ordered = sorted(null_q)
    mean = statistics.fmean(null_q)
    sd = statistics.stdev(null_q) if ok > 1 else 0.0
    summary = NullSummary(
        mean=mean, sd=sd, q05=_quantile(ordered, 0.05), q50=_quantile(ordered, 0.50), q95=_quantile(ordered, 0.95),
        swap_failures=failed,
    )
    result = ExperimentResult(
        experiment_id=eid, outcome=Outcome.COMPLETED, observed_statistic=observed_q, null=summary,
        null_replicates=ok, exceedances=exceed, p_value=(1 + exceed) / (1 + ok),
    )
    delta = observed_q - mean
    return Analysis(**sizes, **diagnostics, suitable=True, result=result, delta_q=delta,
                    z=delta / sd if sd > 0 else None, null_values=tuple(null_q))


def _quantile(ordered: list[float], q: float) -> float:
    """Linear-interpolation quantile (numpy 'linear' / type 7) on sorted data."""
    position = q * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


# --- Full experiment and verdict ----------------------------------------------------------------


class CommunityTestReport(Contract):
    experiment_id: NonEmpty
    graph_id: NonEmpty
    spec_sha256: NonEmpty
    profile: GraphProfile
    primary: Analysis
    secondary: Analysis | None = None
    raw_verdict: Verdict  # exp-v1 §6 rule only
    verdict: Verdict  # after exp-v1.1 rule A (incomplete observation)
    flags: tuple[NonEmpty, ...] = ()
    unknown_pairs: int = Field(default=0, ge=0)
    elapsed_s: float = Field(ge=0)


def verdict(primary: Analysis, secondary: Analysis | None, connected: bool, alpha: float) -> Verdict:
    """Deterministic rule from exp-v1 §6."""
    if not primary.suitable:
        return "abstain"
    if primary.result.p_value > alpha:
        return "not_supported"
    if connected:
        return "supported"
    if secondary is not None and secondary.suitable and secondary.result.p_value <= alpha:
        return "supported"
    return "inconclusive"


DEGREE_CONFOUND_RATIO = 5  # exp-v1.1 rule B: max degree >= 5 x median degree


def run_community_test(graph: nx.Graph, spec: ExperimentSpec, *, spec_sha256: str, unknown_pairs: int = 0
                       ) -> CommunityTestReport:
    """Run primary (whole graph) and, if disconnected, secondary (largest component) analyses.

    `unknown_pairs` is the GraphRecord's count of unobserved pairs (exp-v1.1 rule A).
    """
    if spec.method != "louvain" or spec.null_model != "degree_preserving_double_edge_swap":
        # Defence in depth for specs built without validation (R2): never substitute a method silently.
        raise ValueError(f"method/null {spec.method!r}/{spec.null_model!r} is not implemented; only "
                         "louvain with degree_preserving_double_edge_swap is executed")
    start = time.perf_counter()
    deadline = start + spec.limits.tool_timeout_s
    if graph.number_of_nodes() > spec.limits.max_nodes or graph.number_of_edges() > spec.limits.max_edges:
        raise ValueError("graph exceeds the experiment's size limits")
    info = profile(graph)
    primary = analyse(graph, spec, "whole_graph", deadline)
    connected = info.components == 1 and info.isolated_nodes == 0
    secondary = None
    flags: list[str] = []
    if not connected:
        flags.append("disconnected")
        if primary.suitable:
            largest = graph.subgraph(max(nx.connected_components(graph), key=len)).copy()
            secondary = analyse(largest, spec, "largest_component", deadline)
    if info.edges and info.degree_max >= DEGREE_CONFOUND_RATIO * max(info.degree_median, 1):
        flags.append("degree_confound")
    raw = verdict(primary, secondary, connected, spec.alpha)
    final = raw
    if unknown_pairs:
        flags.append("incomplete_observation")
        if raw == "supported":
            final = "inconclusive"
    return CommunityTestReport(
        experiment_id=spec.experiment_id,
        graph_id=spec.graph_id,
        spec_sha256=spec_sha256,
        profile=info,
        primary=primary,
        secondary=secondary,
        raw_verdict=raw,
        verdict=final,
        flags=tuple(flags),
        unknown_pairs=unknown_pairs,
        elapsed_s=round(time.perf_counter() - start, 6),
    )
