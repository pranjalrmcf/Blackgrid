"""Conservative backdoor review for one supported observed-variable DAG setting."""
from __future__ import annotations

import networkx as nx
from pydantic import Field

from blackgrid.contracts import Contract, NonEmpty


class CausalReview(Contract):
    treatment: NonEmpty
    outcome: NonEmpty
    unit: NonEmpty
    population: NonEmpty
    estimand: str = "ATE"
    edges: tuple[tuple[str, str], ...] = ()
    adjustment: tuple[str, ...] = ()
    observed: tuple[str, ...] = ()
    provenance: NonEmpty
    synthetic: bool = False
    time_order: bool = False
    consistency: bool = False
    positivity: bool = False
    no_hidden_confounding: bool = False
    no_selection_bias: bool = False
    no_interference: bool = False
    measurement_valid: bool = False


def identify(review: CausalReview) -> dict:
    reasons = []
    graph = nx.DiGraph(review.edges)
    graph.add_nodes_from((review.treatment, review.outcome))
    if not nx.is_directed_acyclic_graph(graph):
        reasons.append("DAG is cyclic")
    if review.estimand != "ATE" or review.treatment == review.outcome:
        reasons.append("unsupported estimand or identical treatment/outcome")
    required = ("time_order", "consistency", "positivity", "no_hidden_confounding", "no_selection_bias",
                "no_interference", "measurement_valid")
    reasons += [f"missing assumption: {key}" for key in required if not getattr(review, key)]
    z = set(review.adjustment)
    if not z <= set(review.observed) or not z <= set(graph):
        reasons.append("adjustment variables missing or unobserved")
    if not {review.treatment, review.outcome} <= set(review.observed):
        reasons.append("treatment/outcome unobserved")
    if nx.is_directed_acyclic_graph(graph) and z <= set(graph):
        if z & (nx.descendants(graph, review.treatment) | {review.treatment, review.outcome}):
            reasons.append("adjustment includes treatment, outcome or descendant (mediator/collider risk)")
        else:
            backdoor = graph.copy()
            backdoor.remove_edges_from(list(backdoor.out_edges(review.treatment)))
            if not nx.is_d_separator(backdoor, {review.treatment}, {review.outcome}, z):
                reasons.append("adjustment fails supported backdoor criterion")
    return {"verdict": "not identified" if reasons else
            ("simulated intervention only" if review.synthetic else "identified under stated assumptions"),
            "reasons": reasons, "review": review.model_dump(),
            "limitation": "DAG syntax and backdoor checked; substantive assumptions are supplied, not verified",
            "individual_counterfactuals": False}


def collegemsg_refusal() -> dict:
    return {"verdict": "not identified", "reasons": ["no defined intervention, outcome or identification design"],
            "limitation": "messaging, centrality and edge deletion do not identify causal influence"}
