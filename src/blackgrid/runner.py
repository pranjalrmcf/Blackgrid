"""Run one investigation end to end and write every artifact into a run directory."""

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
from blackgrid.agent import Controller, InvestigationInput, InvestigationResult, flatten, to_claims
from blackgrid.budget import BudgetLedger
from blackgrid.contracts import (
    DataOrigin,
    Environment,
    ExecutionMode,
    RunConfig,
    RunManifest,
    RunStatus,
    canonical_sha256,
)
from blackgrid.providers import (
    MockProvider,
    OpenRouterProvider,
    Provider,
    ReplayProvider,
    api_key_from_env,
    load_env_file,
)
from blackgrid.report import Report, build_report, check_numbers, render_markdown

REPO_ROOT = Path(__file__).resolve().parents[2]


class LiveNotAuthorized(RuntimeError):
    """Live mode was requested without every required authorization."""


def write_json(path: Path, payload: object) -> str:
    data = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


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


def make_provider(config: RunConfig, *, allow_paid: bool, replay_from: Path | None, env_file: Path) -> Provider:
    if config.mode is ExecutionMode.MOCK:
        return MockProvider()
    if config.mode is ExecutionMode.REPLAY:
        if replay_from is None:
            raise LiveNotAuthorized("replay mode needs --replay-from RUN_DIR")
        return ReplayProvider(replay_from / "llm_trace.jsonl")
    if not (config.paid_execution_authorized and allow_paid):
        raise LiveNotAuthorized("live mode needs paid_execution_authorized=true in the config AND --allow-paid")
    load_env_file(env_file)
    key = api_key_from_env()
    if not key:
        raise LiveNotAuthorized("no OPEN_ROUTER_API_KEY (or OPENROUTER_API_KEY) in the environment or .env")
    return OpenRouterProvider(config.llm.model, key, timeout_s=config.llm.request_timeout_s)


@dataclass
class RunOutput:
    run_dir: Path
    manifest: RunManifest
    result: InvestigationResult
    report: Report
    number_violations: list[str]


def run_investigation(inp: InvestigationInput, config: RunConfig, provider: Provider, runs_dir: Path, *,
                      cache_dir: Path | None, run_prefix: str = "", reproduce: str = "",
                      sprint_ledger: Path | None = None, extra_artifacts: dict[str, object] | None = None
                      ) -> RunOutput:
    started = datetime.now(UTC)
    run_id = f"{run_prefix}{started:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    artifacts = {"config.json": write_json(run_dir / "config.json", config.model_dump(mode="json")),
                 "graph_record.json": write_json(run_dir / "graph_record.json", inp.record.model_dump(mode="json"))}
    for name, payload in (extra_artifacts or {}).items():
        artifacts[name] = write_json(run_dir / name, payload)

    pricing = provider.pricing()  # live: fetched now; raises PricingUnavailable before any spend
    ledger = BudgetLedger(limits=config.budget, pricing=pricing,
                          sprint_ledger=sprint_ledger if config.mode is ExecutionMode.LIVE else None)
    controller = Controller(provider, ledger, config.mode, run_dir, config.llm.max_tokens_per_call)
    result, ctx = controller.investigate(inp, config.condition, cache_dir=cache_dir)
    ledger.persist_sprint_total()

    for name, payload in ctx.outputs.items():
        artifacts[name] = write_json(run_dir / name, payload)
    artifacts["investigation.json"] = write_json(run_dir / "investigation.json", result.model_dump(mode="json"))
    artifacts["budget.json"] = write_json(run_dir / "budget.json", {
        "pricing": pricing.model_dump(mode="json"), "limits": config.budget.model_dump(mode="json"),
        "events": ledger.events})
    if (run_dir / "llm_trace.jsonl").is_file():
        artifacts["llm_trace.jsonl"] = hashlib.sha256((run_dir / "llm_trace.jsonl").read_bytes()).hexdigest()

    evidence = flatten({**ctx.outputs, "graph_record.json": inp.record.model_dump(mode="json"),
                        "investigation.json": result.model_dump(mode="json")})
    report = build_report(result, evidence, inp.record, inp.question, run_id, reproduce)
    violations = check_numbers(report, evidence) if result.condition == "validated" else []
    artifacts["report.json"] = write_json(run_dir / "report.json", report.model_dump(mode="json"))
    md = render_markdown(report).encode("utf-8")
    (run_dir / "report.md").write_bytes(md)
    artifacts["report.md"] = hashlib.sha256(md).hexdigest()

    status, reason = result.status, result.failure_reason
    if violations:  # an unsupported number reached the report: never present it as a clean result
        status, reason = RunStatus.FAILED, f"report_number_check_failed: {violations[0][:200]}"
    manifest = RunManifest(
        run_id=run_id, created_utc=started, finished_utc=datetime.now(UTC), status=status,
        failure_reason=reason if status is not RunStatus.COMPLETED else None,
        config_sha256=canonical_sha256(config), environment=capture_environment(),
        seeds={"experiment_master": inp.spec.seed},
        input_hashes={"graph_projection": inp.record.projection_sha256}
        | ({inp.record.source.dataset_id: inp.record.source.sha256} if inp.record.source else {}),
        tool_calls=result.tool_calls, cost=result.cost, artifacts=artifacts,
        claims=to_claims(result, artifacts, DataOrigin(inp.record.origin.value)),
    )
    (run_dir / "manifest.json").write_bytes(manifest.model_dump_json(indent=2).encode("utf-8"))
    from blackgrid.ui import write_run_page  # local import: UI is optional presentation

    write_run_page(run_dir, graph=inp.graph)
    return RunOutput(run_dir=run_dir, manifest=manifest, result=result, report=report, number_violations=violations)
