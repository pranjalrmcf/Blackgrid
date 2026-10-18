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
import socket
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import networkx as nx
from pydantic import ValidationError

from blackgrid.contracts import (
    Contract,
    EdgeStatus,
    ExperimentSpec,
    GraphRecord,
    Outcome,
    ToolCallRecord,
    canonical_sha256,
)
from blackgrid.experiment import DeadlineExceeded, profile, run_community_test
from blackgrid.sensitivity import run_replicate, summarise

TOOL_VERSION = "tools-v1 exp-v1.1 report-v2"
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
    method: Literal["louvain", "greedy_modularity"] = "louvain"


class SensitivityArgs(Contract):
    pass


TOOLS: dict[str, type[Contract]] = {
    "profile_graph": ProfileArgs,
    "community_test": CommunityTestArgs,
    "edge_removal_sensitivity": SensitivityArgs,
}

TOOL_DESCRIPTIONS = {
    "profile_graph": "Aggregate graph profile (sizes, components, degree summary). Args: {}.",
    "community_test": "Preregistered modularity-vs-degree-preserving-null test (exp-v1.1). "
                      "Args: {\"method\": \"louvain\"}. Other parameters are frozen and cannot be changed.",
    "edge_removal_sensitivity": "Prespecified 10% uniform edge-removal sensitivity, 20 replicates. "
                                "Requires community_test first. Args: {}.",
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
}


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
        key = _cache_key(name, args, ctx)
        cached = _cache_get(ctx, key)
        if cached is not None:
            output = cached
        else:
            with network_denied():
                output = _run(name, ctx)
            _cache_put(ctx, key, output)
        artifact = ARTIFACT_NAMES[name]
        ctx.outputs[artifact] = output
        outcome = Outcome.ABSTAINED if output.get("verdict") == "abstain" else Outcome.COMPLETED
        ctx.calls.append(ToolCallRecord(tool=name, args_sha256=args_sha, outcome=outcome,
                                        elapsed_s=round(time.perf_counter() - start, 6), cached=cached is not None))
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
    if name == "edge_removal_sensitivity" and "experiment_report.json" not in ctx.outputs:
        raise ToolRejected("prerequisite missing: run community_test before edge_removal_sensitivity")


def _run(name: str, ctx: ToolContext) -> dict:
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
            runs.append(run_replicate(ctx.graph, ctx.spec, i)[1])
            ctx.calls.append(ToolCallRecord(tool=f"edge_removal_sensitivity[{i}]", args_sha256=_sha([name, i]),
                                            outcome=Outcome.COMPLETED, elapsed_s=round(time.perf_counter() - start, 6)))
        return summarise(ctx.spec, main_raw, runs).model_dump(mode="json")
    raise ToolRejected(f"tool not allowlisted: {name!r}")  # unreachable: parse_request guards


# --- Deterministic result cache -----------------------------------------------------------------


def _cache_key(name: str, args: Contract, ctx: ToolContext) -> str:
    return _sha([TOOL_VERSION, name, args.model_dump(mode="json"), ctx.record.projection_sha256,
                 canonical_sha256(ctx.spec), ctx.unknown_pairs])


def _cache_get(ctx: ToolContext, key: str) -> dict | None:
    if ctx.cache_dir is None:
        return None
    path = ctx.cache_dir / f"{key}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _cache_put(ctx: ToolContext, key: str, output: dict) -> None:
    if ctx.cache_dir is None:
        return
    ctx.cache_dir.mkdir(parents=True, exist_ok=True)
    (ctx.cache_dir / f"{key}.json").write_bytes(json.dumps(output, sort_keys=True).encode("utf-8"))
