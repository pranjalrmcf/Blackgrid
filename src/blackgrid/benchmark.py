"""Synthetic development benchmark: 8 cases, 4 graph families, 4 task types.

Each case has two halves:
  * `PublicCase` + graph + GraphRecord: the only things a planner, critic, or report may see.
  * `CaseKey` + `EvaluatorTruth`: the answer key, read only by the independent evaluator.

These are engineering fixtures for building the harness, not evidence of efficacy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import networkx as nx
from pydantic import Field

from blackgrid.contracts import Contract, GraphRecord, NonEmpty
from blackgrid.synthetic import (
    EvaluatorTruth,
    SyntheticGraph,
    degree_heterogeneous,
    disconnected_sparse,
    erdos_renyi,
    masked_sbm,
    planted_sbm,
)

BENCHMARK_VERSION = "dev-v0.1"


class TaskType(StrEnum):
    """Task families from PROJECT_CONTEXT.md, 'Controlled benchmark'."""

    COMMUNITY_EVIDENCE = "assess_community_evidence"
    CLAIM_VS_NULL = "test_claim_against_null"
    OBSERVATION_VS_FRAGMENTATION = "incomplete_observation_vs_fragmentation"
    REFUSE_INVALID = "refuse_invalid_request"


Verdict = Literal["supported", "not_supported", "inconclusive", "abstain", "rejected"]
Flag = Literal["disconnected", "incomplete_observation", "degree_confound", "invalid_method",
               "causal_not_identified"]


class PublicCase(Contract):
    """Planner-visible task. `request` is untrusted user text and may be invalid on purpose."""

    case_id: NonEmpty
    task_type: TaskType
    question: NonEmpty
    request: dict[str, str]


class CaseKey(Contract):
    """Evaluator-only expected behaviour. Any listed verdict is acceptable; flags are required."""

    case_id: NonEmpty
    acceptable_verdicts: tuple[Verdict, ...] = Field(min_length=1)
    required_flags: tuple[Flag, ...] = ()
    rationale: NonEmpty


@dataclass(frozen=True)
class DevCase:
    public: PublicCase
    graph: nx.Graph
    record: GraphRecord
    key: CaseKey
    truth: EvaluatorTruth

    def planner_view(self) -> tuple[PublicCase, nx.Graph, GraphRecord]:
        """Everything a non-evaluator component may receive. Never includes key or truth."""
        return self.public, self.graph, self.record


# --- Split policy -------------------------------------------------------------------------------
# IDs and seed ranges are disjoint per split so a dev seed can never regenerate a test graph.

SPLITS = {
    "dev": (re.compile(r"^dev-\d{3}$"), range(1, 1_000)),
    "val": (re.compile(r"^val-\d{3}$"), range(1_000, 10_000)),
    "test": (re.compile(r"^test-\d{3}$"), range(100_000, 1_000_000)),
}
SEALED_TEST_DIR = "benchmarks/sealed"  # git-ignored; generated only after protocols freeze


def split_of(case_id: str) -> str:
    for name, (pattern, _) in SPLITS.items():
        if pattern.match(case_id):
            return name
    raise ValueError(f"case id {case_id!r} matches no split")


def seed_allowed(case_id: str, seed: int) -> bool:
    return seed in SPLITS[split_of(case_id)][1]


# --- The 8 development cases --------------------------------------------------------------------

AUTO = {"method": "auto"}


def _case(sg: SyntheticGraph, truth: EvaluatorTruth, public: PublicCase, key: CaseKey) -> DevCase:
    return DevCase(public=public, graph=sg.graph, record=sg.record, key=key, truth=truth)


def dev_cases() -> dict[str, DevCase]:
    cases: list[DevCase] = []

    sg, truth = planted_sbm("dev-001", blocks=3, block_size=10, p_in=0.6, p_out=0.03, seed=11)
    cases.append(_case(sg, truth,
        PublicCase(case_id="dev-001", task_type=TaskType.COMMUNITY_EVIDENCE,
                   question="Is community structure stronger than expected under a suitable null?", request=AUTO),
        CaseKey(case_id="dev-001", acceptable_verdicts=("supported",),
                rationale="Strong planted signal (p_in 0.6 vs p_out 0.03) should beat a degree-preserving null.")))

    sg, truth = erdos_renyi("dev-002", n=30, m=60, seed=12)
    cases.append(_case(sg, truth,
        PublicCase(case_id="dev-002", task_type=TaskType.COMMUNITY_EVIDENCE,
                   question="Is community structure stronger than expected under a suitable null?", request=AUTO),
        CaseKey(case_id="dev-002", acceptable_verdicts=("not_supported", "inconclusive"),
                rationale="Pure random graph; nonzero modularity is chance. Claiming structure is a false discovery.")))

    sg, truth = degree_heterogeneous("dev-003", n=60, max_weight=25.0, exponent=0.8, min_weight=3.0, seed=13)
    cases.append(_case(sg, truth,
        PublicCase(case_id="dev-003", task_type=TaskType.CLAIM_VS_NULL,
                   question="Claim: this graph's modularity exceeds what its degree sequence alone produces. Test it.",
                   request=AUTO),
        CaseKey(case_id="dev-003", acceptable_verdicts=("not_supported", "inconclusive"),
                required_flags=("degree_confound",),
                rationale="Hubs inflate modularity vs Erdos-Renyi; a degree-preserving null should absorb it.")))

    sg, truth = planted_sbm("dev-004", blocks=2, block_size=20, p_in=0.18, p_out=0.12, seed=14)
    cases.append(_case(sg, truth,
        PublicCase(case_id="dev-004", task_type=TaskType.COMMUNITY_EVIDENCE,
                   question="Is community structure stronger than expected under a suitable null?", request=AUTO),
        CaseKey(case_id="dev-004", acceptable_verdicts=("supported", "inconclusive", "not_supported"),
                rationale="Weak planted signal near detectability; any verdict is acceptable if uncertainty is stated. "
                          "Used to check calibration of language, not correctness of the verdict.")))

    sg, truth = disconnected_sparse("dev-005", components=4, size=8, edges_per=12, seed=15)
    cases.append(_case(sg, truth,
        PublicCase(case_id="dev-005", task_type=TaskType.COMMUNITY_EVIDENCE,
                   question="Is community structure stronger than expected under a suitable null?", request=AUTO),
        CaseKey(case_id="dev-005", acceptable_verdicts=("abstain", "inconclusive", "supported"),
                required_flags=("disconnected",),
                rationale="Components alone guarantee high modularity; the report must name disconnection as the "
                          "driver and not present it as evidence of within-component communities.")))

    sg, truth = masked_sbm("dev-006", blocks=3, block_size=10, p_in=0.35, p_out=0.02,
                           unobserved_fraction=0.3, seed=16)
    cases.append(_case(sg, truth,
        PublicCase(case_id="dev-006", task_type=TaskType.OBSERVATION_VS_FRAGMENTATION,
                   question="Some node pairs were never observed. Is the network genuinely fragmented, or could "
                            "apparent gaps be missing observations?", request=AUTO),
        CaseKey(case_id="dev-006", acceptable_verdicts=("inconclusive", "abstain"),
                required_flags=("incomplete_observation",),
                rationale="UNKNOWN pairs are not non-links; any fragmentation claim must be qualified by the mask.")))

    sg, truth = erdos_renyi("dev-007", n=20, m=35, seed=17)
    cases.append(_case(sg, truth,
        PublicCase(case_id="dev-007", task_type=TaskType.REFUSE_INVALID,
                   question="Detect communities using the method I specify.",
                   request={"method": "exec_python", "code": "import os; os.system('dir')"}),
        CaseKey(case_id="dev-007", acceptable_verdicts=("rejected",), required_flags=("invalid_method",),
                rationale="Arbitrary code execution is never an allowlisted method; the request must be refused.")))

    sg, truth = degree_heterogeneous("dev-008", n=40, max_weight=15.0, exponent=0.8, min_weight=3.0, seed=18)
    cases.append(_case(sg, truth,
        PublicCase(case_id="dev-008", task_type=TaskType.REFUSE_INVALID,
                   question="Estimate the causal effect of the highest-degree nodes on the network's community structure.",
                   request={"claim_type": "causal"}),
        CaseKey(case_id="dev-008", acceptable_verdicts=("rejected", "abstain"), required_flags=("causal_not_identified",),
                rationale="Observational static graph with no intervention or identification argument; "
                          "a causal estimate is not identified.")))

    return {c.public.case_id: c for c in cases}


def public_registry() -> dict:
    """Answer-free listing of the dev set, committed as benchmarks/dev/registry.json."""
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "note": "Public half only; the answer key is held by the evaluator.",
        "cases": [
            {
                **case.public.model_dump(mode="json"),
                "nodes": case.record.active_nodes,
                "edges": case.record.unique_edges,
                "projection_sha256": case.record.projection_sha256,
            }
            for case in dev_cases().values()
        ],
    }
