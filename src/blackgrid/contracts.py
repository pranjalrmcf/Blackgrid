"""Typed, validated contracts for graphs, experiments, results, claims, and run manifests.

These encode the Sprint 1 protocol (protocols/sprint01_protocol.md). Every model is frozen and
rejects unknown fields, so a misspelled or smuggled field fails loudly instead of being ignored.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROTOCOL_VERSION = "sprint01-v0.1"

# Frozen by decision D-004: 7 days, 3 days, 1 day, 6 hours.
WINDOW_CANDIDATES_SECONDS: tuple[int, ...] = (604_800, 259_200, 86_400, 21_600)
MAX_ACTIVE_NODES = 1_000
MAX_UNIQUE_EDGES = 10_000
MAX_TOOL_TIMEOUT_S = 60
MAX_WORKER_MEMORY_MB = 2_048

# Paid-pilot ceilings (SPRINT_01.md); they bound a budget, they do not authorize spending.
CEILING_USD_TOTAL = 10.0
CEILING_USD_PER_INVESTIGATION = 0.50
CEILING_LLM_CALLS = 8
CEILING_TOKENS = 20_000
CEILING_RETRIES_PER_CALL = 1
CEILING_REVISION_ROUNDS = 2

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_sha256(model: BaseModel) -> str:
    """Stable hash of a contract: sorted keys, no whitespace, JSON-mode values."""
    payload = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --- Enumerations -------------------------------------------------------------------------------


class EvidenceLevel(StrEnum):
    DESCRIPTIVE = "descriptive"
    PREDICTIVE = "predictive"
    SIMULATED_INTERVENTION = "simulated_intervention"
    IDENTIFIED_CAUSAL = "identified_causal"
    UNSUPPORTED = "unsupported"


class EdgeStatus(StrEnum):
    """Missing observations are not negatives: UNKNOWN and KNOWN_NON_LINK are distinct."""

    OBSERVED = "observed"
    PROXY = "proxy"
    UNKNOWN = "unknown"
    KNOWN_NON_LINK = "known_non_link"


class DataOrigin(StrEnum):
    REAL_PUBLIC = "real_public"
    SYNTHETIC = "synthetic"


class RightsStatus(StrEnum):
    ACCEPTED_LOCAL_NONCOMMERCIAL = "accepted_local_noncommercial"
    UNVERIFIED = "unverified"
    BLOCKED = "blocked"


class ExecutionMode(StrEnum):
    MOCK = "mock"
    REPLAY = "replay"
    LIVE = "live"


class Outcome(StrEnum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"
    FAILED = "failed"


class RunStatus(StrEnum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BUDGET_EXHAUSTED = "budget_exhausted"


# --- Data and graph contracts -------------------------------------------------------------------


class DatasetSource(Contract):
    dataset_id: NonEmpty
    path: NonEmpty  # repository-relative; raw file is read-only
    sha256: Sha256
    source_url: NonEmpty
    citations: tuple[NonEmpty, ...] = Field(min_length=1)
    rights_status: RightsStatus
    rights_decision: NonEmpty  # decision-log ID, e.g. "D-003"
    redistribution_allowed: bool = False

    @model_validator(mode="after")
    def _relative_path(self) -> DatasetSource:
        if self.path.startswith(("/", "\\")) or ":" in self.path:
            raise ValueError("dataset path must be repository-relative")
        return self


class WindowRule(Contract):
    """Deterministic size-only window selection (D-004). Values are fixed by protocol."""

    interval: Literal["half_open"] = "half_open"
    anchor: Literal["min_valid_timestamp"] = "min_valid_timestamp"
    candidate_seconds: tuple[int, ...] = WINDOW_CANDIDATES_SECONDS
    max_active_nodes: int = MAX_ACTIVE_NODES
    max_unique_edges: int = MAX_UNIQUE_EDGES

    @model_validator(mode="after")
    def _frozen(self) -> WindowRule:
        if self.candidate_seconds != WINDOW_CANDIDATES_SECONDS:
            raise ValueError("window candidates are frozen by protocol; version a new protocol")
        if self.max_active_nodes != MAX_ACTIVE_NODES or self.max_unique_edges != MAX_UNIQUE_EDGES:
            raise ValueError("window size caps are frozen by protocol; version a new protocol")
        return self


class ProjectionRule(Contract):
    """Single Sprint 1 projection: simple undirected unweighted graph."""

    directed: Literal[False] = False
    weighted: Literal[False] = False
    repeated_and_reciprocal: Literal["aggregate"] = "aggregate"
    self_loops: Literal["exclude_and_count"] = "exclude_and_count"
    exact_duplicate_rows: Literal["flag_and_keep"] = "flag_and_keep"


class GeneratorSpec(Contract):
    family: Literal["erdos_renyi", "planted_sbm", "degree_heterogeneous", "disconnected_sparse"]
    params: dict[str, float | int]
    seed: int = Field(ge=0)
    version: NonEmpty


class GraphRecord(Contract):
    """Provenance of one analyzable graph. Never carries generator truth (evaluator-only).

    For synthetic graphs only an opaque hash of the GeneratorSpec appears here: the family and
    parameters (e.g. p_in > p_out) would reveal the answer to a community-structure task.
    """

    graph_id: NonEmpty
    origin: DataOrigin
    source: DatasetSource | None = None
    generator_sha256: Sha256 | None = None
    window_start_ts: int | None = None
    window_end_ts: int | None = None  # exclusive
    window_candidate_index: int | None = Field(default=None, ge=0)
    raw_events: int = Field(ge=0)
    window_events: int = Field(ge=0)
    self_loop_events_excluded: int = Field(ge=0)
    exact_duplicate_rows_flagged: int = Field(ge=0)
    active_nodes: int = Field(ge=0)
    unique_edges: int = Field(ge=0)
    edge_status_counts: dict[EdgeStatus, int]
    projection_sha256: Sha256

    @model_validator(mode="after")
    def _consistent(self) -> GraphRecord:
        if self.origin is DataOrigin.REAL_PUBLIC:
            if self.source is None or self.generator_sha256 is not None:
                raise ValueError("real graphs need a dataset source and no generator")
            if self.source.rights_status is not RightsStatus.ACCEPTED_LOCAL_NONCOMMERCIAL:
                raise ValueError("real-data analysis is blocked until usage rights are accepted")
            if None in (self.window_start_ts, self.window_end_ts, self.window_candidate_index):
                raise ValueError("real graphs must record window bounds and the chosen candidate")
            if self.window_end_ts <= self.window_start_ts:
                raise ValueError("window end must follow window start")
        elif self.generator_sha256 is None or self.source is not None:
            raise ValueError("synthetic graphs need a generator hash and no dataset source")
        if self.window_events > self.raw_events:
            raise ValueError("window cannot contain more events than the raw table")
        if self.active_nodes > MAX_ACTIVE_NODES or self.unique_edges > MAX_UNIQUE_EDGES:
            raise ValueError("graph exceeds Sprint 1 size limits")
        if self.edge_status_counts.get(EdgeStatus.OBSERVED, 0) != self.unique_edges:
            raise ValueError("unique_edges must equal the observed-edge count; proxies stay separate")
        return self


# --- Experiment contracts -----------------------------------------------------------------------


class ResourceLimits(Contract):
    tool_timeout_s: int = Field(default=MAX_TOOL_TIMEOUT_S, gt=0, le=MAX_TOOL_TIMEOUT_S)
    worker_memory_mb: int = Field(default=MAX_WORKER_MEMORY_MB, gt=0, le=MAX_WORKER_MEMORY_MB)
    max_nodes: int = Field(default=MAX_ACTIVE_NODES, gt=0, le=MAX_ACTIVE_NODES)
    max_edges: int = Field(default=MAX_UNIQUE_EDGES, gt=0, le=MAX_UNIQUE_EDGES)
    concurrency: Literal[1] = 1


class EdgeRemovalSensitivity(Contract):
    """Prespecified missing-edge sensitivity; a sensitivity analysis, not an uncertainty interval."""

    mechanism: Literal["uniform", "degree_dependent"]
    removal_fraction: float = Field(gt=0.0, le=0.5)
    replicates: int = Field(ge=1, le=1_000)


class SuitabilityRule(Contract):
    """Abstention thresholds from protocols/sprint01_experiment.md §5 (exp-v1)."""

    min_edges: int = Field(default=20, ge=1)
    min_nonisolated_nodes: int = Field(default=10, ge=2)
    max_failed_null_fraction: float = Field(default=0.05, ge=0, le=1)
    min_distinct_null_fraction: float = Field(default=0.95, ge=0, le=1)


class ExperimentSpec(Contract):
    experiment_id: NonEmpty
    graph_id: NonEmpty
    status: Literal["exploratory", "confirmatory"]
    hypothesis: NonEmpty
    competing_explanations: tuple[NonEmpty, ...] = Field(min_length=1)
    task: Literal["community_structure_vs_null"]
    method: Literal["louvain", "greedy_modularity"]
    statistic: Literal["modularity"]
    null_model: Literal["degree_preserving_double_edge_swap", "erdos_renyi_gnm"]
    null_replicates: int = Field(ge=19, le=10_000)
    swaps_per_edge: float = Field(default=10.0, gt=0, le=100)
    swap_attempt_factor: int = Field(default=100, ge=1, le=1_000)
    optimizer_restarts: int = Field(default=5, ge=1, le=20)
    resolution: Literal[1.0] = 1.0
    alpha: float = Field(default=0.05, gt=0, le=0.1)
    seed: int = Field(ge=0)
    same_procedure_on_nulls: Literal[True] = True
    secondary_largest_component: Literal[True] = True
    suitability: SuitabilityRule = SuitabilityRule()
    sensitivity: EdgeRemovalSensitivity
    limits: ResourceLimits = ResourceLimits()

    @property
    def p_value_resolution(self) -> float:
        """Smallest attainable Monte Carlo p-value, 1/(1 + replicates)."""
        return 1.0 / (1 + self.null_replicates)


# --- Results and claims -------------------------------------------------------------------------


class NullSummary(Contract):
    mean: float
    sd: float = Field(ge=0)
    q05: float
    q50: float
    q95: float
    swap_failures: int = Field(default=0, ge=0)


class ExperimentResult(Contract):
    experiment_id: NonEmpty
    outcome: Outcome
    reason: str | None = None
    observed_statistic: float | None = None
    null: NullSummary | None = None
    null_replicates: int | None = Field(default=None, ge=1)
    exceedances: int | None = Field(default=None, ge=0)
    p_value: float | None = Field(default=None, gt=0, le=1)
    artifacts: dict[NonEmpty, Sha256] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> ExperimentResult:
        stats = (self.observed_statistic, self.null, self.null_replicates, self.exceedances, self.p_value)
        if self.outcome is Outcome.COMPLETED:
            if any(s is None for s in stats):
                raise ValueError("completed results need statistic, null summary, replicates, exceedances, p-value")
            if self.exceedances > self.null_replicates:
                raise ValueError("exceedances cannot exceed replicates")
            expected = (1 + self.exceedances) / (1 + self.null_replicates)
            if abs(self.p_value - expected) > 1e-12:
                raise ValueError("p_value must equal (1 + exceedances) / (1 + replicates)")
        elif not self.reason:
            raise ValueError("failed or abstained results must state a reason")
        return self


class EvidenceLink(Contract):
    artifact: NonEmpty
    sha256: Sha256
    field: NonEmpty  # JSON pointer or key inside the artifact


class Identification(Contract):
    estimand: NonEmpty
    assumptions: tuple[NonEmpty, ...] = Field(min_length=1)
    interference: NonEmpty
    positivity: NonEmpty


class Claim(Contract):
    claim_id: NonEmpty
    text: NonEmpty
    evidence_level: EvidenceLevel
    origin: DataOrigin  # synthetic and real evidence are never pooled
    evidence: tuple[EvidenceLink, ...] = ()
    limitations: tuple[NonEmpty, ...] = ()
    identification: Identification | None = None

    @model_validator(mode="after")
    def _supported(self) -> Claim:
        if self.evidence_level is not EvidenceLevel.UNSUPPORTED and not self.evidence:
            raise ValueError("factual claims must link to recorded evidence")
        if self.evidence_level is EvidenceLevel.IDENTIFIED_CAUSAL and self.identification is None:
            raise ValueError("causal claims require an estimand and identification argument")
        return self


# --- Run configuration and manifest -------------------------------------------------------------


class BudgetLimits(Contract):
    max_usd_total: float = Field(default=CEILING_USD_TOTAL, ge=0, le=CEILING_USD_TOTAL)
    max_usd_per_investigation: float = Field(
        default=CEILING_USD_PER_INVESTIGATION, ge=0, le=CEILING_USD_PER_INVESTIGATION
    )
    max_llm_calls: int = Field(default=CEILING_LLM_CALLS, ge=0, le=CEILING_LLM_CALLS)
    max_tokens: int = Field(default=CEILING_TOKENS, ge=0, le=CEILING_TOKENS)
    max_retries_per_call: int = Field(default=CEILING_RETRIES_PER_CALL, ge=0, le=CEILING_RETRIES_PER_CALL)
    max_revision_rounds: int = Field(default=CEILING_REVISION_ROUNDS, ge=0, le=CEILING_REVISION_ROUNDS)


class RunConfig(Contract):
    protocol_version: Literal["sprint01-v0.1"] = PROTOCOL_VERSION
    mode: ExecutionMode = ExecutionMode.MOCK
    paid_execution_authorized: bool = False
    network_allowed: Literal[False] = False
    dataset: DatasetSource
    window: WindowRule = WindowRule()
    projection: ProjectionRule = ProjectionRule()
    experiment: ExperimentSpec | None = None  # frozen on Day 5 before execution
    limits: ResourceLimits = ResourceLimits()
    budget: BudgetLimits = BudgetLimits()

    @model_validator(mode="after")
    def _authorized(self) -> RunConfig:
        if self.mode is ExecutionMode.LIVE and not self.paid_execution_authorized:
            raise ValueError("live mode requires explicit paid-execution authorization")
        return self


class ToolCallRecord(Contract):
    tool: NonEmpty
    args_sha256: Sha256
    outcome: Outcome
    elapsed_s: float = Field(ge=0)
    error: str | None = None


class CostRecord(Contract):
    mode: ExecutionMode
    llm_calls: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_usd: float = Field(default=0.0, ge=0)
    actual_usd: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _offline_is_free(self) -> CostRecord:
        if self.mode is not ExecutionMode.LIVE and (self.actual_usd or self.estimated_usd):
            raise ValueError("mock and replay runs must record zero monetary cost")
        return self


class Environment(Contract):
    python: NonEmpty
    platform: NonEmpty
    blackgrid_version: NonEmpty
    dependency_lock_sha256: Sha256 | None
    source_commit: str | None
    source_dirty: bool | None


class RunManifest(Contract):
    run_id: NonEmpty
    protocol_version: Literal["sprint01-v0.1"] = PROTOCOL_VERSION
    created_utc: datetime
    finished_utc: datetime | None = None
    status: RunStatus
    failure_reason: str | None = None
    config_sha256: Sha256
    environment: Environment
    seeds: dict[NonEmpty, int] = Field(default_factory=dict)
    input_hashes: dict[NonEmpty, Sha256] = Field(default_factory=dict)
    tool_calls: tuple[ToolCallRecord, ...] = ()
    cost: CostRecord
    artifacts: dict[NonEmpty, Sha256] = Field(default_factory=dict)
    claims: tuple[Claim, ...] = ()

    @model_validator(mode="after")
    def _explained(self) -> RunManifest:
        if self.created_utc.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware UTC")
        if self.status is not RunStatus.COMPLETED and not self.failure_reason:
            raise ValueError("non-completed runs must record why")
        return self
