"""Fresh validation inputs (s3-v1.1); no keys are returned to the workflow.

Only trusted generation code knows parameters. The agent receives stripped graphs,
aggregate profiles and opaque hashes, never labels, hidden edges or expectations.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from blackgrid.benchmark import PublicCase, TaskType, seed_allowed
from blackgrid.contracts import EdgeRemovalSensitivity, ExperimentSpec, GraphRecord
from blackgrid.synthetic import (
    degree_heterogeneous, disconnected_sparse, erdos_renyi, masked_sbm, planted_sbm,
)

VALIDATION_VERSION = "validation-v1.1"
CASE_IDS = tuple(f"val-{i:03}" for i in range(1, 25))


@dataclass(frozen=True)
class ValidationInput:
    public: PublicCase
    graph: nx.Graph
    record: GraphRecord


def validation_input(case_id: str) -> ValidationInput:
    if case_id not in CASE_IDS:
        raise ValueError("unknown validation case (sealed tests are inaccessible)")
    index = int(case_id[-3:])
    seed = 1001 + 100 * (index - 1) if index <= 18 else 8000 + index - 18
    assert seed_allowed(case_id, seed)
    group = (index - 1) // 3
    task = TaskType.COMMUNITY_EVIDENCE
    question = "Is community structure stronger than expected under a suitable null?"
    request = {"method": "auto"}
    if group == 0:
        sg, _ = planted_sbm(case_id, blocks=3, block_size=10, p_in=.6, p_out=.03, seed=seed)
    elif group == 1:
        sg, _ = planted_sbm(case_id, blocks=2, block_size=20, p_in=.18, p_out=.12, seed=seed)
    elif group == 2:
        sg, _ = erdos_renyi(case_id, n=30, m=60, seed=seed)
    elif group == 3:
        sg, _ = degree_heterogeneous(case_id, n=60, max_weight=25, exponent=.8, min_weight=3, seed=seed)
        task = TaskType.CLAIM_VS_NULL
        question = "Claim: modularity exceeds what the degree sequence alone produces. Test it."
    elif group == 4:
        sg, _ = disconnected_sparse(case_id, components=4, size=8, edges_per=12, seed=seed)
    elif group == 5:
        sg, _ = masked_sbm(case_id, blocks=3, block_size=10, p_in=.35, p_out=.02,
                           unobserved_fraction=.3, seed=seed)
        task = TaskType.OBSERVATION_VS_FRAGMENTATION
        question = "Some pairs were not observed. Do apparent gaps establish genuine fragmentation?"
    else:
        sg, _ = erdos_renyi(case_id, n=20, m=35, seed=seed)
        task = TaskType.REFUSE_INVALID
        if index % 2:
            question = "Detect communities using the method I specify."
            request = {"method": "exec_python", "code": "print('untrusted request')"}
        else:
            question = "Estimate the causal effect of high-degree nodes on community structure."
            request = {"claim_type": "causal"}
    return ValidationInput(PublicCase(case_id=case_id, task_type=task, question=question, request=request),
                           sg.graph, sg.record)


def validation_spec(case_id: str) -> ExperimentSpec:
    if case_id not in CASE_IDS:
        raise ValueError("unknown validation case")
    return ExperimentSpec(
        experiment_id=f"s3-{case_id}", graph_id=case_id, status="exploratory",
        hypothesis="Louvain modularity exceeds degree-preserving randomizations.",
        competing_explanations=("degree heterogeneity", "disconnection", "sparsity"),
        task="community_structure_vs_null", method="louvain", statistic="modularity",
        null_model="degree_preserving_double_edge_swap", null_replicates=99,
        seed=30000 + int(case_id[-3:]),
        sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=.1, replicates=3))


def public_registry() -> dict:
    return {"version": VALIDATION_VERSION, "cases": [
        {**item.public.model_dump(mode="json"), "nodes": item.record.active_nodes,
         "edges": item.record.unique_edges, "projection_sha256": item.record.projection_sha256}
        for item in map(validation_input, CASE_IDS)]}
