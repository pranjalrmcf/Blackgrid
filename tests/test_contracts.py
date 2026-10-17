"""Scientific-invariant checks for the Sprint 1 contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from blackgrid.contracts import (
    Claim,
    CostRecord,
    DataOrigin,
    EdgeRemovalSensitivity,
    EdgeStatus,
    EvidenceLevel,
    EvidenceLink,
    ExecutionMode,
    ExperimentResult,
    ExperimentSpec,
    GeneratorSpec,
    GraphRecord,
    Identification,
    NullSummary,
    Outcome,
    RightsStatus,
    RunConfig,
    WindowRule,
    canonical_sha256,
)

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "collegemsg_sprint01.json"
HASH = "a" * 64


def config_dict() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def link() -> EvidenceLink:
    return EvidenceLink(artifact="result.json", sha256=HASH, field="/observed_statistic")


def synthetic_graph(**overrides) -> GraphRecord:
    fields = dict(
        graph_id="g1",
        origin=DataOrigin.SYNTHETIC,
        generator=GeneratorSpec(family="planted_sbm", params={"n": 60, "k": 3}, seed=7, version="0"),
        raw_events=100,
        window_events=100,
        self_loop_events_excluded=0,
        exact_duplicate_rows_flagged=0,
        active_nodes=60,
        unique_edges=90,
        edge_status_counts={EdgeStatus.OBSERVED: 90},
        projection_sha256=HASH,
    )
    fields.update(overrides)
    return GraphRecord(**fields)


def spec(**overrides) -> ExperimentSpec:
    fields = dict(
        experiment_id="e1",
        graph_id="g1",
        status="exploratory",
        hypothesis="Modularity exceeds the degree-preserving null.",
        competing_explanations=("Degree heterogeneity alone produces the observed modularity.",),
        task="community_structure_vs_null",
        method="louvain",
        statistic="modularity",
        null_model="degree_preserving_double_edge_swap",
        null_replicates=99,
        seed=1,
        sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=0.1, replicates=20),
    )
    fields.update(overrides)
    return ExperimentSpec(**fields)


# --- configuration ------------------------------------------------------------------------------


def test_shipped_config_is_valid_offline_mock():
    config = RunConfig.model_validate(config_dict())
    assert config.mode is ExecutionMode.MOCK
    assert config.network_allowed is False
    assert config.dataset.redistribution_allowed is False


def test_config_hash_is_stable_and_content_sensitive():
    a = RunConfig.model_validate(config_dict())
    b = RunConfig.model_validate(config_dict())
    assert canonical_sha256(a) == canonical_sha256(b)
    changed = config_dict()
    changed["dataset"]["dataset_id"] = "other"
    assert canonical_sha256(RunConfig.model_validate(changed)) != canonical_sha256(a)


def test_unknown_fields_are_rejected():
    data = config_dict()
    data["answer_key_path"] = "truth.json"
    with pytest.raises(ValidationError):
        RunConfig.model_validate(data)


def test_live_mode_requires_paid_authorization():
    data = config_dict() | {"mode": "live"}
    with pytest.raises(ValidationError, match="authorization"):
        RunConfig.model_validate(data)


def test_network_cannot_be_enabled():
    with pytest.raises(ValidationError):
        RunConfig.model_validate(config_dict() | {"network_allowed": True})


@pytest.mark.parametrize("field,value", [("max_usd_total", 10.01), ("max_llm_calls", 9), ("max_tokens", 20_001)])
def test_budget_cannot_exceed_sprint_ceilings(field, value):
    with pytest.raises(ValidationError):
        RunConfig.model_validate(config_dict() | {"budget": {field: value}})


def test_absolute_dataset_path_rejected():
    data = config_dict()
    data["dataset"]["path"] = "C:/Blackgrid/data/CollegeMsg.txt/CollegeMsg.txt"
    with pytest.raises(ValidationError, match="relative"):
        RunConfig.model_validate(data)


# --- window and graph ---------------------------------------------------------------------------


def test_window_rule_is_frozen():
    assert WindowRule().candidate_seconds == (7 * 86_400, 3 * 86_400, 86_400, 6 * 3_600)
    with pytest.raises(ValidationError, match="frozen"):
        WindowRule(candidate_seconds=(14 * 86_400,))
    with pytest.raises(ValidationError, match="frozen"):
        WindowRule(max_unique_edges=20_000)


def test_graph_record_cannot_carry_generator_truth():
    with pytest.raises(ValidationError):
        synthetic_graph(planted_labels={"0": 0})


def test_oversized_graph_rejected():
    with pytest.raises(ValidationError, match="size limits"):
        synthetic_graph(unique_edges=10_001, edge_status_counts={EdgeStatus.OBSERVED: 10_001})


def test_proxy_edges_are_not_counted_as_observed():
    synthetic_graph(edge_status_counts={EdgeStatus.OBSERVED: 90, EdgeStatus.PROXY: 5, EdgeStatus.UNKNOWN: 40})
    with pytest.raises(ValidationError, match="observed-edge"):
        synthetic_graph(edge_status_counts={EdgeStatus.OBSERVED: 85, EdgeStatus.PROXY: 5})


def test_unknown_and_known_non_link_are_distinct_statuses():
    assert EdgeStatus.UNKNOWN != EdgeStatus.KNOWN_NON_LINK


def test_real_graph_blocked_without_accepted_rights():
    source = RunConfig.model_validate(config_dict()).dataset
    blocked = source.model_copy(update={"rights_status": RightsStatus.UNVERIFIED})
    real = dict(
        origin=DataOrigin.REAL_PUBLIC,
        generator=None,
        window_start_ts=0,
        window_end_ts=604_800,
        window_candidate_index=0,
    )
    synthetic_graph(**real, source=source)
    with pytest.raises(ValidationError, match="rights"):
        synthetic_graph(**real, source=blocked)


# --- experiment and result ----------------------------------------------------------------------


def test_p_value_resolution():
    assert spec(null_replicates=99).p_value_resolution == pytest.approx(0.01)


def test_unlisted_method_and_tiny_null_rejected():
    with pytest.raises(ValidationError):
        spec(method="arbitrary_python")
    with pytest.raises(ValidationError):
        spec(null_replicates=5)


def test_tool_timeout_cannot_exceed_cap():
    with pytest.raises(ValidationError):
        spec(limits={"tool_timeout_s": 61})


def result(**overrides) -> ExperimentResult:
    fields = dict(
        experiment_id="e1",
        outcome=Outcome.COMPLETED,
        observed_statistic=0.42,
        null=NullSummary(mean=0.30, sd=0.02, q05=0.27, q50=0.30, q95=0.33),
        null_replicates=99,
        exceedances=0,
        p_value=0.01,
    )
    fields.update(overrides)
    return ExperimentResult(**fields)


def test_p_value_must_match_monte_carlo_formula():
    result()
    with pytest.raises(ValidationError, match="exceedances"):
        result(p_value=0.0001)


def test_exceedances_bounded_by_replicates():
    with pytest.raises(ValidationError, match="cannot exceed"):
        result(exceedances=100, p_value=1.0)


def test_failure_and_abstention_must_explain():
    ExperimentResult(experiment_id="e1", outcome=Outcome.ABSTAINED, reason="graph too sparse for null")
    with pytest.raises(ValidationError, match="reason"):
        ExperimentResult(experiment_id="e1", outcome=Outcome.FAILED)


# --- claims and cost ----------------------------------------------------------------------------


def test_factual_claim_requires_evidence():
    with pytest.raises(ValidationError, match="evidence"):
        Claim(claim_id="c1", text="Modularity is high.", evidence_level=EvidenceLevel.DESCRIPTIVE,
              origin=DataOrigin.REAL_PUBLIC)
    Claim(claim_id="c1", text="Insufficient evidence.", evidence_level=EvidenceLevel.UNSUPPORTED,
          origin=DataOrigin.REAL_PUBLIC)


def test_causal_claim_requires_identification():
    kwargs = dict(claim_id="c2", text="Hubs cause cohesion.", evidence_level=EvidenceLevel.IDENTIFIED_CAUSAL,
                  origin=DataOrigin.SYNTHETIC, evidence=(link(),))
    with pytest.raises(ValidationError, match="identification"):
        Claim(**kwargs)
    Claim(**kwargs, identification=Identification(
        estimand="ATE of hub removal on modularity", assumptions=("known SCM",),
        interference="exposure mapping defined by simulator", positivity="all units treatable"))


def test_offline_runs_record_zero_cost():
    CostRecord(mode=ExecutionMode.MOCK)
    with pytest.raises(ValidationError, match="zero"):
        CostRecord(mode=ExecutionMode.MOCK, actual_usd=0.01)
