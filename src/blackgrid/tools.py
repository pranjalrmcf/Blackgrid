"""Allowlisted tool registry and guarded executor (Sprint 1 Day 7).

Agents never run code. A planner may only *name* one of the registered tools with arguments that
pass a strict schema. The executor then:

* rejects unknown tools, malformed or oversized requests, and unexpected arguments;
* stops the whole investigation on any attempt to reach answer keys or generator truth;
* refuses graphs above the size caps before any computation;
* runs trusted, deterministic tools with network access disabled in-process and a cooperative
  wall-clock deadline per call.

Limits that are *not* enforced here, stated plainly: there is no OS-level sandbox, and worker
memory is not capped on Windows. The tools are trusted in-repo code; the graph-size cap is the
memory proxy. A subprocess would not be a sandbox either (AGENTS.md).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import socket
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import networkx as nx
from pydantic import Field, ValidationError

from blackgrid.contracts import (
    Contract,
    EdgeStatus,
    ExperimentSpec,
    GraphRecord,
    Outcome,
    ToolCallRecord,
    canonical_sha256,
)
from blackgrid.experiment import CommunityTestReport, DeadlineExceeded, GraphProfile, profile, run_community_test
from blackgrid.sensitivity import R_SENS, SensitivitySummary, run_replicate, summarise
from blackgrid.structural import StructuralResult, compute as compute_structural

TOOL_VERSION = "tools-v2 structural-v1 exp-v1.1 report-v2"
MAX_REQUEST_BYTES = 2_000
ANSWER_KEY_MARKERS = ("answer", "truth", "label", "sealed", "case_key", "casekey", "evaluator", "planted",
                      "hidden_edge", "generator_spec")


class ToolRejected(Exception):
    """The request is not allowed; recorded as a failed tool call. The run may continue."""


class AnswerKeyAccess(Exception):
    """A request tried to reach evaluator-only data. The investigation must stop."""


class NetworkDenied(PermissionError):
    """A tool tried to open a network connection."""


# --- Argument schemas (extra fields forbidden) --------------------------------------------------


class ProfileArgs(Contract):
    pass


class CommunityTestArgs(Contract):
    method: Literal["louvain"] = "louvain"  # the only implemented optimizer (R2)


class SensitivityArgs(Contract):
    pass


class _ForecastProfileArgs(Contract):
    pass


class _LinkPredictionArgs(Contract):
    task: Literal["new_pair", "repeat_pair"]
    method: str = Field(default="selected", max_length=64, pattern=r"^[a-z_0-9.A-Z]+$")


class _PredictionCompareArgs(Contract):
    task: Literal["new_pair", "repeat_pair"]
    split: Literal["validation", "test", "rolling"] = "validation"


TOOLS: dict[str, type[Contract]] = {
    "profile_graph": ProfileArgs,
    "community_test": CommunityTestArgs,
    "edge_removal_sensitivity": SensitivityArgs,
    "node_centrality": ProfileArgs,
    "community_partition": ProfileArgs,
    "community_bridge": ProfileArgs,
    "ranking_sensitivity": ProfileArgs,
    "temporal_profile": _ForecastProfileArgs,
    "link_prediction": _LinkPredictionArgs,
    "prediction_compare": _PredictionCompareArgs,
}

def tool_descriptions(spec: ExperimentSpec, sensitivity_null_replicates: int = R_SENS) -> dict[str, str]:
    """What the planner is told about each tool, generated from the settings that will actually run (R4/§5.6)."""
    sens = spec.sensitivity
    return {
        "profile_graph": "Aggregate graph profile (sizes, components, degree summary). Args: {}.",
        "node_centrality": "Local degree and normalized betweenness rankings; aggregate summary only to model. Args: {}.",
        "community_partition": "Descriptive Louvain partition, five restarts; not a significance test. Args: {}.",
        "community_bridge": "Cross-community degree and fraction; requires community_partition. Not influence. Args: {}.",
        "ranking_sensitivity": "Three fixed 10% uniform removals; tie-inclusive top-five Jaccard and Spearman. Requires a ranking. Args: {}.",
        "community_test": f"Frozen modularity test ({spec.experiment_id}): Louvain modularity vs a degree-preserving "
                          f"double-edge-swap null, {spec.null_replicates} null replicates. "
                          "Args: {\"method\": \"louvain\"}. Other parameters are frozen and cannot be changed.",
        "temporal_profile": "Forecast history summary at the fixed cutoff (last observed event): event, node, pair and "
                            "candidate counts. Args: {}.",
        "link_prediction": "Rank known-node pairs for the next fixed horizon. Args: {\"task\": \"new_pair\" (never "
                           "messaged before) or \"repeat_pair\" (messaged before), \"method\": \"selected\" (the "
                           "confirmed logistic_v2 model where available) or a registered heuristic}. Returns aggregates only; scores are "
                           "uncalibrated rankings. Cutoff and horizon cannot be changed.",
        "prediction_compare": "Evaluation aggregates. Args: {\"task\": same task, \"split\": \"rolling\" (rolling "
                              "windows here plus confirmation on an unseen dataset; use with the selected logistic_v2), "
                              "\"test\" (prediction-v1 sealed test of the v1 methods) or \"validation\"}. Labels are "
                              "never available.",
        "edge_removal_sensitivity": f"Prespecified {sens.removal_fraction:.0%} {sens.mechanism} edge-removal "
                                    f"sensitivity, {sens.replicates} replicates with {sensitivity_null_replicates} "
                                    "nulls each. Requires community_test first. Args: {}.",
    }


# --- Network guard ------------------------------------------------------------------------------


@contextlib.contextmanager
def network_denied() -> Iterator[None]:
    """Make outbound connections raise while trusted tools run (an in-process guard, not a sandbox)."""

    def refuse(*_args: Any, **_kwargs: Any) -> None:
        raise NetworkDenied("network access is denied inside tool execution")

    saved = socket.socket.connect, socket.socket.connect_ex, socket.create_connection
    socket.socket.connect = refuse  # type: ignore[method-assign]
    socket.socket.connect_ex = refuse  # type: ignore[method-assign]
    socket.create_connection = refuse  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection = saved  # type: ignore[assignment]


# --- Context and results ------------------------------------------------------------------------


@dataclass
class ToolContext:
    graph: nx.Graph
    record: GraphRecord
    spec: ExperimentSpec
    cache_dir: Path | None = None
    forecast: Any = None  # zero-argument factory -> prediction.service.PredictionTools (forecast family only)
    local_dir: Path | None = None  # where a local-only pair ranking may be written
    sensitivity_null_replicates: int = R_SENS  # exp-v2-full may lower it (runtime)
    outputs: dict[str, dict] = field(default_factory=dict)  # artifact name -> JSON payload
    calls: list[ToolCallRecord] = field(default_factory=list)

    @property
    def unknown_pairs(self) -> int:
        return self.record.edge_status_counts.get(EdgeStatus.UNKNOWN, 0)


@dataclass(frozen=True)
class ToolResult:
    tool: str
    artifact: str
    output: dict


ARTIFACT_NAMES = {
    "profile_graph": "graph_profile.json",
    "community_test": "experiment_report.json",
    "edge_removal_sensitivity": "sensitivity.json",
    "node_centrality": "node_centrality.json",
    "community_partition": "community_partition.json",
    "community_bridge": "community_bridge.json",
    "ranking_sensitivity": "ranking_sensitivity.json",
    "temporal_profile": "temporal_profile.json",
    "link_prediction": "link_prediction.json",
    "prediction_compare": "prediction_compare.json",
}
FORECAST_TOOLS = ("temporal_profile", "link_prediction", "prediction_compare")


def _sha(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def parse_request(raw: object) -> tuple[str, Contract]:
    """Validate an untrusted tool request. Raises AnswerKeyAccess or ToolRejected."""
    try:
        text = json.dumps(raw, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ToolRejected(f"malformed request: not JSON-serialisable ({exc})") from exc
    if any(marker in text.lower() for marker in ANSWER_KEY_MARKERS):
        raise AnswerKeyAccess("request references evaluator-only data")
    if len(text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise ToolRejected(f"oversized request: {len(text)} bytes > {MAX_REQUEST_BYTES}")
    if not isinstance(raw, dict) or set(raw) - {"tool", "args"} or "tool" not in raw:
        raise ToolRejected("malformed request: expected {\"tool\": str, \"args\": object}")
    name, args = raw["tool"], raw.get("args", {})
    if not isinstance(name, str) or name not in TOOLS:
        raise ToolRejected(f"tool not allowlisted: {str(name)[:64]!r}")
    if not isinstance(args, dict):
        raise ToolRejected("malformed request: args must be an object")
    try:
        return name, TOOLS[name].model_validate(args)
    except ValidationError as exc:
        raise ToolRejected(f"invalid arguments for {name}: {exc.errors()[0]['msg']}") from exc


def execute(raw: object, ctx: ToolContext) -> ToolResult:
    """Validate and run one tool request, recording a ToolCallRecord whatever happens."""
    start = time.perf_counter()
    name = raw.get("tool", "?") if isinstance(raw, dict) else "?"
    args_sha = _sha(raw)
    try:
        name, args = parse_request(raw)
        _check_prerequisites(name, args, ctx)
        if name in FORECAST_TOOLS:  # Sprint 6: deterministic forecast tools; no cache, aggregates only
            cached = rejected = None
            with network_denied():
                output = _run_forecast(name, args, ctx)
        else:
            key = _cache_key(name, args, ctx)
            cached, rejected = _cache_get(ctx, name, key)
            if cached is not None:
                output = cached
            else:
                with network_denied():
                    output = _run(name, ctx)
                _cache_put(ctx, name, key, output)
        artifact = ARTIFACT_NAMES[name]
        ctx.outputs[artifact] = output
        outcome = Outcome.ABSTAINED if output.get("verdict") == "abstain" else Outcome.COMPLETED
        ctx.calls.append(ToolCallRecord(tool=name, args_sha256=args_sha, outcome=outcome,
                                        elapsed_s=round(time.perf_counter() - start, 6), cached=cached is not None,
                                        cache_rejected=rejected))
        return ToolResult(tool=name, artifact=artifact, output=output)
    except AnswerKeyAccess:
        ctx.calls.append(ToolCallRecord(tool=str(name)[:64], args_sha256=args_sha, outcome=Outcome.FAILED,
                                        elapsed_s=round(time.perf_counter() - start, 6),
                                        error="answer_key_access_attempt"))
        raise
    except (ToolRejected, DeadlineExceeded, NetworkDenied, ValueError) as exc:
        ctx.calls.append(ToolCallRecord(tool=str(name)[:64], args_sha256=args_sha, outcome=Outcome.FAILED,
                                        elapsed_s=round(time.perf_counter() - start, 6),
                                        error=f"{type(exc).__name__}: {exc}"[:300]))
        raise ToolRejected(f"{type(exc).__name__}: {exc}") from exc


def _check_prerequisites(name: str, args: Contract, ctx: ToolContext) -> None:
    limits = ctx.spec.limits
    if ctx.graph.number_of_nodes() > limits.max_nodes or ctx.graph.number_of_edges() > limits.max_edges:
        raise ToolRejected("oversized graph: exceeds node/edge caps")
    if name == "community_test" and args.method != ctx.spec.method:
        raise ToolRejected(f"method {args.method!r} deviates from the preregistered spec ({ctx.spec.method!r})")
    if name in ("node_centrality", "community_bridge", "ranking_sensitivity") and not len(ctx.graph):
        raise ToolRejected("empty graph has no nodes to rank")
    if name == "edge_removal_sensitivity" and "experiment_report.json" not in ctx.outputs:
        raise ToolRejected("prerequisite missing: run community_test before edge_removal_sensitivity")
    if name == "community_bridge" and "community_partition.json" not in ctx.outputs:
        raise ToolRejected("prerequisite missing: run community_partition before community_bridge")
    if name == "ranking_sensitivity" and not any(x in ctx.outputs for x in ("node_centrality.json", "community_bridge.json")):
        raise ToolRejected("prerequisite missing: ranking required")


def _run_forecast(name: str, args: Contract, ctx: ToolContext) -> dict:
    """Call the frozen prediction service. Pair rankings go only to a local file, never to the model."""
    from blackgrid.prediction.service import PredictionToolRejected

    if ctx.forecast is None:
        raise ToolRejected("forecast tools are available only for forecast questions on approved event data")
    tools = ctx.forecast()
    try:
        if name == "temporal_profile":
            return tools.temporal_profile(args)
        if name == "link_prediction":
            local = ctx.local_dir / "local_ranking.json" if ctx.local_dir else None
            return tools.link_prediction(args, local_out=local) | {
                "history": "all validated events up to the last observed event; the data-scope selector does not apply"}
        return tools.prediction_compare(args)
    except PredictionToolRejected as exc:
        raise ToolRejected(str(exc)) from exc


def _run(name: str, ctx: ToolContext) -> dict:
    if name in ("node_centrality", "community_partition", "community_bridge", "ranking_sensitivity"):
        return compute_structural(name, ctx.graph, ctx.record.projection_sha256, ctx.spec.seed,
                                  ctx.spec.limits.tool_timeout_s, ctx.outputs)
    if name == "profile_graph":
        return profile(ctx.graph).model_dump(mode="json")
    if name == "community_test":
        report = run_community_test(ctx.graph, ctx.spec, spec_sha256=canonical_sha256(ctx.spec),
                                    unknown_pairs=ctx.unknown_pairs)
        return report.model_dump(mode="json")
    if name == "edge_removal_sensitivity":
        main_raw = ctx.outputs["experiment_report.json"]["raw_verdict"]
        runs = []
        for i in range(ctx.spec.sensitivity.replicates):  # each replicate is its own bounded call
            start = time.perf_counter()
            runs.append(run_replicate(ctx.graph, ctx.spec, i, ctx.sensitivity_null_replicates)[1])
            ctx.calls.append(ToolCallRecord(tool=f"edge_removal_sensitivity[{i}]", args_sha256=_sha([name, i]),
                                            outcome=Outcome.COMPLETED, elapsed_s=round(time.perf_counter() - start, 6)))
        return summarise(ctx.spec, main_raw, runs, ctx.sensitivity_null_replicates).model_dump(mode="json")
    raise ToolRejected(f"tool not allowlisted: {name!r}")  # unreachable: parse_request guards


# --- Deterministic result cache -----------------------------------------------------------------


def _cache_key(name: str, args: Contract, ctx: ToolContext) -> str:
    extra = [] if ctx.sensitivity_null_replicates == R_SENS else [ctx.sensitivity_null_replicates]
    if name in ("community_bridge", "ranking_sensitivity"):
        extra += [_sha({k: v for k, v in ctx.outputs.items() if k in
                        ("community_partition.json", "community_bridge.json", "node_centrality.json")})]
    return _sha([TOOL_VERSION, name, args.model_dump(mode="json"), ctx.record.projection_sha256,
                 canonical_sha256(ctx.spec), ctx.unknown_pairs, *extra])


CACHE_VERSION = 2  # v2: integrity envelope + schema/invariant validation (Sprint 4 R3); v1 entries are stale


def _payload_sha(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _identity(name: str, key: str, ctx: ToolContext) -> dict:
    return {"cache_version": CACHE_VERSION, "key": key, "tool": name, "tool_version": TOOL_VERSION,
            "projection_sha256": ctx.record.projection_sha256, "spec_sha256": canonical_sha256(ctx.spec)}


def _check_payload(name: str, payload: dict, ctx: ToolContext) -> None:
    """Schema and scientific invariants a reusable result must satisfy for *this* graph and spec."""
    nodes, edges = ctx.graph.number_of_nodes(), ctx.graph.number_of_edges()
    if name == "profile_graph":
        prof = GraphProfile.model_validate(payload)
        if (prof.nodes, prof.edges) != (nodes, edges):
            raise ValueError(f"profile describes {prof.nodes} nodes/{prof.edges} edges, graph has {nodes}/{edges}")
    elif name == "community_test":
        report = CommunityTestReport.model_validate(payload)
        if report.spec_sha256 != canonical_sha256(ctx.spec) or report.graph_id != ctx.spec.graph_id:
            raise ValueError("experiment report belongs to a different spec or graph")
        if (report.profile.nodes, report.profile.edges, report.primary.nodes, report.primary.edges) !=                 (nodes, edges, nodes, edges):
            raise ValueError("experiment report sizes do not match the graph")
        if report.unknown_pairs != ctx.unknown_pairs:
            raise ValueError("experiment report used a different unknown-pair count")
        result = report.primary.result
        if result.null_replicates is not None and result.null_replicates > ctx.spec.null_replicates:
            raise ValueError("experiment report has more null replicates than the spec allows")
    elif name == "edge_removal_sensitivity":
        summary = SensitivitySummary.model_validate(payload)
        sens = ctx.spec.sensitivity
        expected = (sens.mechanism, sens.removal_fraction, sens.replicates, ctx.sensitivity_null_replicates)
        if (summary.mechanism, summary.removal_fraction, summary.replicates, summary.null_replicates_per_run)                 != expected:
            raise ValueError("sensitivity summary settings do not match the spec")
        main = ctx.outputs.get("experiment_report.json", {}).get("raw_verdict")
        if summary.main_raw_verdict != main or sum(summary.verdict_counts.values()) != summary.replicates:
            raise ValueError("sensitivity summary is inconsistent with the main result")
    elif name in ("node_centrality", "community_partition", "community_bridge", "ranking_sensitivity"):
        report = StructuralResult.model_validate(payload)
        if (report.tool, report.graph_sha256, report.nodes, report.edges, report.seed) != (
                name, ctx.record.projection_sha256, nodes, edges, ctx.spec.seed):
            raise ValueError("structural output identity mismatch")
        if name != "ranking_sensitivity" and ({r.node for r in report.rows} != {str(n) for n in ctx.graph}
                                               or len(report.rows) != nodes):
            raise ValueError("structural rows must cover exactly the graph")
    else:
        raise ValueError(f"no cache validator for {name!r}")


def _cache_get(ctx: ToolContext, name: str, key: str) -> tuple[dict | None, str | None]:
    """(payload, None) for a valid hit, (None, None) for a miss, (None, reason) for a rejected entry.

    Policy: a corrupt, malformed, stale, mismatched or invariant-violating entry is never used. It is
    renamed to `<key>.json.rejected-<time>` (kept for diagnosis), the reason is recorded on the tool
    call, and the result is recomputed under the same protocol. A hash is an integrity check against
    accidents, not protection against someone able to rewrite every local file.
    """
    if ctx.cache_dir is None:
        return None, None
    path = ctx.cache_dir / f"{key}.json"
    if not path.is_file():
        return None, None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(entry, dict) or "payload" not in entry:
            raise ValueError("not a v2 cache envelope (stale version)")
        expected = _identity(name, key, ctx)
        wrong = [k for k, v in expected.items() if entry.get(k) != v]
        if wrong:
            raise ValueError(f"identity mismatch: {', '.join(wrong)}")
        payload = entry["payload"]
        if not isinstance(payload, dict) or entry.get("payload_sha256") != _payload_sha(payload):
            raise ValueError("payload hash mismatch")
        _check_payload(name, payload, ctx)
        return payload, None
    except (OSError, ValueError, TypeError) as exc:  # pydantic's ValidationError is a ValueError
        reason = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else 'empty'}"
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        try:
            path.replace(path.with_name(f"{path.name}.rejected-{stamp}"))
        except OSError:
            pass
        return None, reason


def _cache_put(ctx: ToolContext, name: str, key: str, output: dict) -> None:
    if ctx.cache_dir is None:
        return
    ctx.cache_dir.mkdir(parents=True, exist_ok=True)
    entry = _identity(name, key, ctx) | {"payload_sha256": _payload_sha(output), "payload": output}
    path = ctx.cache_dir / f"{key}.json"
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with tmp.open("wb") as fh:  # write-then-rename: an interrupted write never looks like a valid entry
        fh.write(json.dumps(entry, sort_keys=True).encode("utf-8"))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
