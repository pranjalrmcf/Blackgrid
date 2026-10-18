"""Prespecified missing-edge sensitivity (exp-v1 §9, amended exp-v1.1 §11 C-D).

Each replicate removes a fixed fraction of observed edges uniformly at random. Removed pairs
become UNKNOWN (unobserved), never non-links. The full experiment is re-run on each reduced graph
with R_sens null replicates. This is a sensitivity analysis: it shows how fragile the verdict is to
missing edges under one assumed mechanism, and recovers no hidden truth.
"""

from __future__ import annotations

import random
import statistics
from collections import Counter
from collections.abc import Callable

import networkx as nx
from pydantic import Field

from blackgrid.contracts import Contract, EdgeStatus, ExperimentSpec, NonEmpty, canonical_sha256
from blackgrid.experiment import CommunityTestReport, derive_seed, run_community_test

R_SENS = 99  # exp-v1.1 §11 C


class ReplicateSummary(Contract):
    index: int
    removed_edges: int
    edge_status_counts: dict[EdgeStatus, int]
    observed_q: float | None
    null_mean: float | None
    delta_q: float | None
    p_value: float | None
    lcc_p_value: float | None
    raw_verdict: NonEmpty
    elapsed_s: float


class SensitivitySummary(Contract):
    mechanism: NonEmpty
    removal_fraction: float
    replicates: int
    null_replicates_per_run: int
    main_raw_verdict: NonEmpty
    agreement: int = Field(ge=0)
    agreement_fraction: float = Field(ge=0, le=1)
    verdict_counts: dict[str, int]
    observed_q_min: float | None
    observed_q_median: float | None
    observed_q_max: float | None
    delta_q_min: float | None
    delta_q_median: float | None
    delta_q_max: float | None
    runs: tuple[ReplicateSummary, ...]
    label: NonEmpty = "sensitivity analysis (assumed uniform missingness); not an uncertainty interval"


def remove_edges(graph: nx.Graph, fraction: float, rng: random.Random) -> tuple[nx.Graph, list[tuple]]:
    """Copy the graph without a uniformly chosen `fraction` of its edges (nodes are kept)."""
    edges = sorted(tuple(sorted(e)) for e in graph.edges())
    k = round(fraction * len(edges))
    removed = rng.sample(edges, k)
    reduced = nx.Graph()
    reduced.add_nodes_from(sorted(graph.nodes()))
    reduced.add_edges_from(set(edges) - set(removed))
    return reduced, removed


def sensitivity_spec(spec: ExperimentSpec, r_sens: int = R_SENS) -> ExperimentSpec:
    return spec.model_copy(update={"null_replicates": r_sens, "experiment_id": f"{spec.experiment_id}:sensitivity"})


def run_replicate(graph: nx.Graph, spec: ExperimentSpec, index: int, r_sens: int = R_SENS
                  ) -> tuple[CommunityTestReport, ReplicateSummary]:
    """One reduced-graph experiment: a single bounded tool call under the spec's timeout."""
    sens = sensitivity_spec(spec, r_sens)
    rng = random.Random(derive_seed(spec.seed, "sensitivity", index))
    reduced, removed = remove_edges(graph, spec.sensitivity.removal_fraction, rng)
    report = run_community_test(reduced, sens, spec_sha256=canonical_sha256(sens), unknown_pairs=len(removed))
    p = report.primary
    summary = ReplicateSummary(
        index=index,
        removed_edges=len(removed),
        edge_status_counts={EdgeStatus.OBSERVED: reduced.number_of_edges(), EdgeStatus.UNKNOWN: len(removed)},
        observed_q=p.result.observed_statistic,
        null_mean=p.result.null.mean if p.result.null else None,
        delta_q=p.delta_q,
        p_value=p.result.p_value,
        lcc_p_value=report.secondary.result.p_value if report.secondary else None,
        raw_verdict=report.raw_verdict,
        elapsed_s=report.elapsed_s,
    )
    return report, summary


def run_sensitivity(graph: nx.Graph, spec: ExperimentSpec, main_raw_verdict: str,
                    on_replicate: Callable[[ReplicateSummary], None] | None = None) -> SensitivitySummary:
    if spec.sensitivity.mechanism != "uniform":
        raise ValueError("only the prespecified uniform mechanism is implemented in Sprint 1")
    runs = []
    for index in range(spec.sensitivity.replicates):
        _, summary = run_replicate(graph, spec, index)
        runs.append(summary)
        if on_replicate:
            on_replicate(summary)
    return summarise(spec, main_raw_verdict, runs)


def summarise(spec: ExperimentSpec, main_raw_verdict: str, runs: list[ReplicateSummary], r_sens: int = R_SENS
              ) -> SensitivitySummary:
    def stats(values: list[float]) -> tuple[float | None, float | None, float | None]:
        return (min(values), statistics.median(values), max(values)) if values else (None, None, None)

    q = stats([r.observed_q for r in runs if r.observed_q is not None])
    d = stats([r.delta_q for r in runs if r.delta_q is not None])
    agree = sum(r.raw_verdict == main_raw_verdict for r in runs)
    return SensitivitySummary(
        mechanism=spec.sensitivity.mechanism,
        removal_fraction=spec.sensitivity.removal_fraction,
        replicates=len(runs),
        null_replicates_per_run=r_sens,
        main_raw_verdict=main_raw_verdict,
        agreement=agree,
        agreement_fraction=agree / len(runs) if runs else 0.0,
        verdict_counts=dict(sorted(Counter(r.raw_verdict for r in runs).items())),
        observed_q_min=q[0], observed_q_median=q[1], observed_q_max=q[2],
        delta_q_min=d[0], delta_q_median=d[1], delta_q_max=d[2],
        runs=tuple(runs),
    )
