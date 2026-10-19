"""Run, resume, and finalize durable investigations (Sprint 2: through the LangGraph workflow)."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from blackgrid import __version__
from blackgrid.agent.roles import InvestigationInput, InvestigationResult, flatten, to_claims
from blackgrid.contracts import (
    DataOrigin,
    Environment,
    ExecutionMode,
    RunConfig,
    RunManifest,
    RunStatus,
    canonical_sha256,
)
from blackgrid.agent.providers import (
    MockProvider,
    OpenRouterProvider,
    Provider,
    ReplayProvider,
    api_key_from_env,
    load_env_file,
    model_from_env,
)
from blackgrid.agent.report import Report, build_report, check_numbers, render_markdown
from blackgrid.workflow.api import Outcome, RunSpec, approval_scope, identity_of, open_services, resume, start
from blackgrid.workflow.engine import atomic_write
from blackgrid.workflow.engine import write_json as _atomic_json

REPO_ROOT = Path(__file__).resolve().parents[3]  # src/blackgrid/workflow/runner.py -> repository root


class LiveNotAuthorized(RuntimeError):
    """Live mode was requested without every required authorization."""


def write_json(path: Path, payload: object) -> str:
    return _atomic_json(path, payload)


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, timeout=10,
                             check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def capture_environment() -> Environment:
    lock = REPO_ROOT / "uv.lock"
    status = _git("status", "--porcelain")
    return Environment(
        python=platform.python_version(), platform=platform.platform(), blackgrid_version=__version__,
        dependency_lock_sha256=hashlib.sha256(lock.read_bytes()).hexdigest() if lock.is_file() else None,
        source_commit=_git("rev-parse", "HEAD") or None, source_dirty=None if status is None else bool(status))


def apply_env_model(config: RunConfig, env_file: Path) -> RunConfig:
    """Live mode: a model set in the environment or .env (OPEN_ROUTER_MODEL) overrides the config.

    The override is applied to the config itself, so the run's config.json and config hash record
    the model that was actually used.
    """
    if config.mode is not ExecutionMode.LIVE:
        return config
    load_env_file(env_file)
    model = model_from_env()
    if not model or model == config.llm.model:
        return config
    data = config.model_dump(mode="json")
    data["llm"]["model"] = model
    return RunConfig.model_validate(data)


def make_provider(config: RunConfig, *, allow_paid: bool, replay_from: Path | None, env_file: Path) -> Provider:
    """Provider for a run. Live needs the config flag; per-run authorization is checked by the workflow."""
    if config.mode is ExecutionMode.MOCK:
        return MockProvider()
    if config.mode is ExecutionMode.REPLAY:
        if replay_from is None:
            raise LiveNotAuthorized("replay mode needs --replay-from RUN_DIR")
        return ReplayProvider(replay_from / "llm_trace.jsonl")
    if not config.paid_execution_authorized:
        raise LiveNotAuthorized("live mode needs paid_execution_authorized=true in the config")
    load_env_file(env_file)
    key = api_key_from_env()
    if not key:
        raise LiveNotAuthorized("no OPEN_ROUTER_API_KEY (or OPENROUTER_API_KEY) in the environment or .env")
    return OpenRouterProvider(config.llm.model, key, timeout_s=config.llm.request_timeout_s,
                              reasoning_max_tokens=config.llm.reasoning_max_tokens,
                              provider_ignore=config.llm.provider_ignore, provider_sort=config.llm.provider_sort)


def model_name(config: RunConfig, replay_from: Path | None) -> str:
    """The model identity, known without contacting any provider."""
    if config.mode is ExecutionMode.MOCK:
        return MockProvider.model
    if config.mode is ExecutionMode.REPLAY:
        return ReplayProvider(replay_from / "llm_trace.jsonl").model if replay_from else "replay"
    return config.llm.model


# --- input references (how a resumed run reloads its graph) -------------------------------------


def load_input(input_ref: dict, run_dir: Path) -> InvestigationInput:
    inp = _load_input(input_ref, run_dir)
    if "inquiry" in input_ref:
        inp.question = input_ref["inquiry"]["question"]
        inp.request = dict(input_ref["inquiry"]["request"])
    elif "research_evidence" in input_ref:
        config = RunConfig.model_validate_json((run_dir / "config.json").read_text(encoding="utf-8"))
        inp.question = config.question
        inp.request = {"method": "auto", "family": "research", "planning_mode": config.planning_mode}
    return inp


def _load_input(input_ref: dict, run_dir: Path) -> InvestigationInput:
    """Rebuild the scientific input from its approved local source (never from the checkpoint)."""
    kind = input_ref.get("kind")
    if kind == "collegemsg":
        from blackgrid.data.collegemsg import BoundedGraph, build_graph

        config = RunConfig.model_validate_json((run_dir / "config.json").read_text(encoding="utf-8"))
        built = build_graph(Path(input_ref["data_root"]), config)  # first window or full dataset
        if not isinstance(built, BoundedGraph):
            raise ValueError("the window rule no longer selects a graph")
        return InvestigationInput(case_id=built.record.graph_id, question=config.question,
                                  request={"method": "auto", "family": config.investigation_family,
                                           "planning_mode": config.planning_mode}, graph=built.graph, record=built.record,
                                  spec=config.experiment)
    if kind == "dev":
        from blackgrid.evaluation.benchmark import dev_cases
        from blackgrid.evaluation.pilot import dev_spec

        case = dev_cases()[input_ref["case_id"]]
        public, graph, record = case.planner_view()  # never the answer key
        return InvestigationInput(case_id=public.case_id, question=public.question, request=public.request,
                                  graph=graph, record=record, spec=dev_spec(case))
    if kind == "validation":
        from blackgrid.evaluation.validation import validation_input, validation_spec

        case = validation_input(input_ref["case_id"])
        return InvestigationInput(case_id=case.public.case_id, question=case.public.question,
                                  request=case.public.request, graph=case.graph, record=case.record,
                                  spec=validation_spec(case.public.case_id))
    if kind == "sprint5":
        from blackgrid.evaluation.sprint5 import evaluation_input
        inp = evaluation_input(input_ref["index"])
        config = RunConfig.model_validate_json((run_dir / "config.json").read_text(encoding="utf-8"))
        inp.request["planning_mode"] = config.planning_mode
        return inp
    if kind == "sprint5-live":
        from blackgrid.evaluation.sprint5_live import live_input
        inp = live_input(input_ref["index"], input_ref.get("version", "s5-live-v1"))
        config = RunConfig.model_validate_json((run_dir / "config.json").read_text(encoding="utf-8"))
        inp.request["planning_mode"] = config.planning_mode
        return inp
    raise ValueError(f"run input {kind!r} cannot be reloaded")


# --- finalization: report, manifest, UI (idempotent) ------------------------------------------------


KNOWN_ARTIFACTS = ("config.json", "graph_record.json", "input_profile.json", "window_selection.json", "full_scope.json",
                   "research_contract.json", "reliability_audit.json", "belief_update.json", "experiment_decision.json",
                   "causal_identification_check.json",
                   "structural_contract.json", "forecast_contract.json", "temporal_profile.json", "link_prediction.json",
                   "prediction_compare.json", "local_ranking.json",
                   "node_centrality.json", "community_partition.json", "community_bridge.json", "ranking_sensitivity.json",
                   "graph_profile.json", "experiment_report.json", "sensitivity.json", "investigation.json",
                   "budget.json", "llm_trace.jsonl", "report.json", "report.md")


def finalizer(config: RunConfig, reproduce: str):
    def on_finalize(rt, state, result: InvestigationResult, ctx) -> tuple[str, str] | None:
        inp = rt.inputs(state)
        run_dir = rt.run_dir
        if result.family == "forecast":
            from blackgrid.prediction import PREDICTION_VERSION
            from blackgrid.prediction.claims import PRED_CRITIC_VERSION
            from blackgrid.workflow.engine import FORECAST_EVALUATION

            freeze = run_dir.parent / FORECAST_EVALUATION / "freeze.json"
            protocol = json.loads(freeze.read_text(encoding="utf-8")).get("protocol_sha256") if freeze.is_file() else None
            write_json(run_dir / "forecast_contract.json", {
                "version": PREDICTION_VERSION, "claim_checker": PRED_CRITIC_VERSION, "evaluation": FORECAST_EVALUATION,
                "evaluation_protocol_sha256": protocol, "cutoff": "last observed event (fixed by the system)",
                "pair_rankings": "local_ranking.json, local only; never sent to a model or exported"})
        elif result.family == "research":
            write_json(run_dir / "research_contract.json", {
                "version": "research-v1", "scope": "saved synthetic demonstration only",
                "source": state.get("input_ref", {}).get("research_evidence"),
                "new_experiments_executed": False, "real_forecast_voi": "unavailable"})
        elif result.family != "community":
            from blackgrid.analysis.structural import StructuralSpec
            write_json(run_dir / "structural_contract.json", StructuralSpec(family=result.family,
                       graph_sha256=inp.record.projection_sha256, seed=inp.spec.seed).model_dump(mode="json"))
        write_json(run_dir / "investigation.json", result.model_dump(mode="json"))
        write_json(run_dir / "budget.json", {"pricing": rt.pricing().model_dump(mode="json")
                                             if rt._provider is not None else None,
                                             "limits": config.budget.model_dump(mode="json"),
                                             "events": rt.store.events(rt.run_id)})
        evidence = flatten({**ctx.outputs, "graph_record.json": inp.record.model_dump(mode="json"),
                            "investigation.json": result.model_dump(mode="json")})
        report = build_report(result, evidence, inp.record, inp.question, rt.run_id, reproduce)
        violations = check_numbers(report, evidence) if result.condition == "validated" else []
        write_json(run_dir / "report.json", report.model_dump(mode="json"))
        atomic_write(run_dir / "report.md", render_markdown(report).encode("utf-8"))
        rt.fault("during_finalize")
        status, reason = result.status, result.failure_reason
        if violations:  # an unsupported number reached the report: never present it as a clean result
            status, reason = RunStatus.FAILED, f"report_number_check_failed: {violations[0][:200]}"
        artifacts = {name: hashlib.sha256((run_dir / name).read_bytes()).hexdigest()
                     for name in KNOWN_ARTIFACTS if (run_dir / name).is_file()}
        manifest = RunManifest(
            run_id=rt.run_id, created_utc=datetime.fromisoformat(rt.store.run(rt.run_id)["created_utc"]),
            finished_utc=datetime.now(UTC), status=status,
            failure_reason=reason if status is not RunStatus.COMPLETED else None,
            config_sha256=canonical_sha256(config), environment=capture_environment(),
            seeds={"experiment_master": inp.spec.seed},
            input_hashes={"graph_projection": inp.record.projection_sha256}
            | ({inp.record.source.dataset_id: inp.record.source.sha256} if inp.record.source else {}),
            tool_calls=result.tool_calls, cost=result.cost, artifacts=artifacts,
            claims=to_claims(result, artifacts, DataOrigin.SYNTHETIC if result.family == "research"
                             else DataOrigin(inp.record.origin.value)))
        atomic_write(run_dir / "manifest.json", manifest.model_dump_json(indent=2).encode("utf-8"))
        return (status.value, reason) if violations else None
    return on_finalize


def renderer(rt, state) -> None:
    from blackgrid.console.ui import write_run_page  # presentation only

    write_run_page(rt.run_dir, graph=rt.inputs(state).graph)


@dataclass
class RunOutput:
    run_dir: Path
    outcome: Outcome
    manifest: RunManifest | None
    result: InvestigationResult | None
    report: Report | None


def _output(outcome: Outcome) -> RunOutput:
    def load(name: str, model):
        path = outcome.run_dir / name
        return model.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None

    finished = outcome.status != "paused"
    return RunOutput(run_dir=outcome.run_dir, outcome=outcome,
                     manifest=load("manifest.json", RunManifest) if finished else None,
                     result=load("investigation.json", InvestigationResult) if finished else outcome.result,
                     report=load("report.json", Report) if finished else None)


def run_spec(config: RunConfig, run_dir: Path, *, provider_factory, model: str, cache_dir: Path | None,
             reproduce: str) -> RunSpec:
    return RunSpec(limits=config.budget, mode=config.mode, condition=config.condition,
                   max_tokens=config.llm.max_tokens_per_call, model=model, config_sha256=canonical_sha256(config),
                   provider_factory=provider_factory, loader=lambda ref: load_input(ref, run_dir),
                   cache_dir=cache_dir, on_finalize=finalizer(config, reproduce), on_render=renderer,
                   sensitivity_null_replicates=config.sensitivity_null_replicates, deadline_s=config.deadline_s)


def run_investigation(inp: InvestigationInput, config: RunConfig, provider: Provider | None, runs_dir: Path, *,
                      cache_dir: Path | None, input_ref: dict, run_prefix: str = "", reproduce: str = "",
                      extra_artifacts: dict[str, object] | None = None, allow_paid: bool = False,
                      replay_from: Path | None = None, env_file: Path | None = None,
                      faults: set[str] | None = None, parent_run: str | None = None) -> RunOutput:
    """Start a durable workflow run. Live runs without --allow-paid pause before the first paid call."""
    started = datetime.now(UTC)
    run_id = f"{run_prefix}{started:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    from blackgrid.agent.inquiry import family
    input_ref = input_ref | {"inquiry": {"question": inp.question, "request": dict(inp.request)}}
    config = config.model_copy(update={"question": inp.question})
    if inp.request.get("family") == "auto" or family(inp.question, inp.request) == "research":
        # Trusted system choice, never taken from question/model arguments. Pin identity before planning.
        reference = (REPO_ROOT / "runs" / "sprint7-final").resolve()
        manifest = reference / "sprint7_manifest.json"
        input_ref = input_ref | {"research_evidence": {
            "path": str(reference), "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()
            if manifest.is_file() else "unavailable"}}
    write_json(run_dir / "config.json", config.model_dump(mode="json"))
    write_json(run_dir / "graph_record.json", inp.record.model_dump(mode="json"))
    for name, payload in (extra_artifacts or {}).items():
        write_json(run_dir / name, payload)
    write_json(run_dir / "run_source.json", {"input_ref": input_ref, "reproduce": reproduce,
                                             "replay_from": str(replay_from) if replay_from else None})

    if provider is None:
        def factory() -> Provider:
            return make_provider(config, allow_paid=True, replay_from=replay_from,
                                 env_file=env_file or REPO_ROOT / ".env")
        model = model_name(config, replay_from)
    else:
        def factory() -> Provider:
            return provider
        model = getattr(provider, "model", "unknown")
    spec = run_spec(config, run_dir, provider_factory=factory, model=model, cache_dir=cache_dir, reproduce=reproduce)
    services = open_services(runs_dir)
    try:
        scope = None
        if config.mode is ExecutionMode.LIVE and allow_paid and config.paid_execution_authorized:
            scope = approval_scope(spec, identity_of(inp, spec.config_sha256, model, config.condition, config.mode,
                                                     input_ref))
        outcome = start(inp, input_ref, spec, services, run_dir, run_id=run_id, authorization=scope,
                        parent_run=parent_run, faults=faults)
    finally:
        services.close()
    return _output(outcome)


def resume_investigation(run_id: str, runs_dir: Path, *, decision: dict | None = None, allow_paid: bool = False,
                         force_unlock: bool = False, cache_dir: Path | None = None, env_file: Path | None = None,
                         provider: Provider | None = None, faults: set[str] | None = None) -> RunOutput:
    """Resume a paused or interrupted run exactly where its durable records say it stopped."""
    services = open_services(runs_dir)
    try:
        row = services.store.run(run_id)
        run_dir = Path(row["run_dir"])
        config = RunConfig.model_validate_json((run_dir / "config.json").read_text(encoding="utf-8"))
        source = json.loads((run_dir / "run_source.json").read_text(encoding="utf-8"))
        replay_from = Path(source["replay_from"]) if source.get("replay_from") else None
        if provider is None:
            def factory() -> Provider:
                return make_provider(config, allow_paid=True, replay_from=replay_from,
                                     env_file=env_file or REPO_ROOT / ".env")
            model = model_name(config, replay_from)
        else:
            def factory() -> Provider:
                return provider
            model = getattr(provider, "model", "unknown")
        spec = run_spec(config, run_dir, provider_factory=factory, model=model, cache_dir=cache_dir,
                        reproduce=source.get("reproduce", ""))
        if allow_paid and config.mode is ExecutionMode.LIVE:
            # --allow-paid grants a fresh, scoped authorization; it answers an authorization pause only.
            scope = approval_scope(spec, json.loads(row["identity_json"]))
            services.store.set_authorization(run_id, scope)
            pause = json.loads(row["pause_json"]) if row["pause_json"] else {}
            if decision is None and pause.get("kind") == "authorization":
                decision = {"decision": "approve", "scope": scope}
        outcome = resume(run_id, spec, services, decision=decision, force_unlock=force_unlock, faults=faults)
    finally:
        services.close()
    return _output(outcome)
