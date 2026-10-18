"""Command-line entry point.

    blackgrid validate CONFIG                 validate a run configuration and print its hash
    blackgrid run CONFIG [options]            full CollegeMsg investigation (mock mode by default)
    blackgrid pilot                           mock pilot: tool_only vs validated on 8 dev cases
    blackgrid ui                              rebuild the HTML console pages and runs/index.html

`run` options:
    --mode mock|live|replay    override the config's mode
    --condition validated|tool_only
    --allow-paid               required (with paid_execution_authorized=true) for live mode
    --replay-from RUN_DIR      replay the recorded LLM responses of an earlier run
    --no-cache                 recompute every tool result

Exit codes: 0 completed, 1 invalid input or not authorized, 2 run did not complete
(abstained, failed, or budget exhausted; see the manifest).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from blackgrid.agent import InvestigationInput
from blackgrid.collegemsg import BoundedGraph, DataIntegrityError, build_bounded_graph
from blackgrid.contracts import (
    CostRecord,
    Outcome,
    RunConfig,
    RunManifest,
    RunStatus,
    ToolCallRecord,
    canonical_sha256,
)
from blackgrid.providers import PricingUnavailable
from blackgrid.runner import REPO_ROOT, LiveNotAuthorized, capture_environment, make_provider, run_investigation, write_json

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_RUN_FAILED = 2


def load_config(path: Path) -> RunConfig:
    return RunConfig.model_validate_json(path.read_text(encoding="utf-8"))


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except (OSError, ValidationError, ValueError) as exc:
        print(f"invalid config: {exc}", file=sys.stderr)
        return EXIT_INVALID
    print(f"valid  protocol={config.protocol_version}  mode={config.mode}  sha256={canonical_sha256(config)}")
    return EXIT_OK


def _early_record(args: argparse.Namespace, config: RunConfig, status: RunStatus, reason: str,
                  calls: list[ToolCallRecord], extra: dict[str, object]) -> int:
    """Manifest for runs that stop before the investigation (load failure, window abstention)."""
    started = datetime.now(UTC)
    run_dir = args.runs_dir / f"{started:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    run_dir.mkdir(parents=True)
    artifacts = {"config.json": write_json(run_dir / "config.json", config.model_dump(mode="json"))}
    artifacts |= {name: write_json(run_dir / name, payload) for name, payload in extra.items()}
    manifest = RunManifest(run_id=run_dir.name, created_utc=started, finished_utc=datetime.now(UTC), status=status,
                           failure_reason=reason, config_sha256=canonical_sha256(config),
                           environment=capture_environment(),
                           input_hashes={config.dataset.dataset_id: config.dataset.sha256},
                           tool_calls=tuple(calls), cost=CostRecord(mode=config.mode), artifacts=artifacts)
    (run_dir / "manifest.json").write_bytes(manifest.model_dump_json(indent=2).encode("utf-8"))
    print(f"run {run_dir.name}: {status.value} ({reason})", file=sys.stderr)
    print(run_dir)
    return EXIT_RUN_FAILED


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
        overrides = {k: v for k, v in (("mode", args.mode), ("condition", args.condition)) if v}
        if overrides:
            config = RunConfig.model_validate(config.model_dump(mode="json") | overrides)
    except (OSError, ValidationError, ValueError) as exc:
        print(f"invalid config: {exc}", file=sys.stderr)
        return EXIT_INVALID
    if config.experiment is None:
        print("invalid config: no frozen experiment specification", file=sys.stderr)
        return EXIT_INVALID

    try:
        provider = make_provider(config, allow_paid=args.allow_paid, replay_from=args.replay_from,
                                 env_file=args.env_file)
        pricing = provider.pricing()  # live: confirm current pricing before anything else
    except (LiveNotAuthorized, PricingUnavailable, OSError) as exc:
        print(f"not started: {exc}", file=sys.stderr)
        return EXIT_INVALID
    if config.mode.value == "live":
        print(f"live mode: {pricing.model} at ${pricing.prompt_usd_per_token * 1e6:.4f}/M input, "
              f"${pricing.completion_usd_per_token * 1e6:.4f}/M output tokens; caps: "
              f"{config.budget.max_llm_calls} calls, {config.budget.max_tokens} tokens, "
              f"${config.budget.max_usd_per_investigation} per run, ${config.budget.max_usd_total} sprint",
              file=sys.stderr)

    clock = time.perf_counter()
    try:
        built = build_bounded_graph(args.data_root, config.dataset, config.window)
    except (DataIntegrityError, ValidationError) as exc:
        call = ToolCallRecord(tool="collegemsg.build_bounded_graph", args_sha256=canonical_sha256(config.window),
                              outcome=Outcome.FAILED, elapsed_s=round(time.perf_counter() - clock, 6),
                              error=f"{type(exc).__name__}: {exc}"[:300])
        return _early_record(args, config, RunStatus.FAILED, f"load_failed: {type(exc).__name__}", [call], {})
    if not isinstance(built, BoundedGraph):
        call = ToolCallRecord(tool="collegemsg.build_bounded_graph", args_sha256=canonical_sha256(config.window),
                              outcome=Outcome.ABSTAINED, elapsed_s=round(time.perf_counter() - clock, 6))
        return _early_record(args, config, RunStatus.ABSTAINED, f"window_abstention: {built.abstention_reason}",
                             [call], {"window_selection.json": built.summary()})
    if config.experiment.graph_id != built.record.graph_id:
        print(f"invalid config: spec targets {config.experiment.graph_id!r}, graph is {built.record.graph_id!r}",
              file=sys.stderr)
        return EXIT_INVALID

    inp = InvestigationInput(case_id=built.record.graph_id, question=config.question, request={"method": "auto"},
                             graph=built.graph, record=built.record, spec=config.experiment)
    reproduce = f"uv run --frozen blackgrid run {args.config.as_posix()} --mode {config.mode.value}"
    print(f"running {config.condition} investigation in {config.mode.value} mode "
          "(experiment + 20 sensitivity replicates; first run takes about 2 minutes)...", file=sys.stderr)
    out = run_investigation(inp, config, provider, args.runs_dir, cache_dir=None if args.no_cache else args.cache_dir,
                            reproduce=reproduce, sprint_ledger=args.runs_dir / "spend_ledger.json",
                            extra_artifacts={"input_profile.json": built.table.summary(),
                                             "window_selection.json": built.selection.summary()})
    m = out.manifest
    print(f"run {m.run_id}: {m.status.value} · verdict {out.result.verdict} · "
          f"LLM calls {m.cost.llm_calls} · cost ${m.cost.actual_usd:.4f}"
          + (f" · {m.failure_reason}" if m.failure_reason else ""), file=sys.stderr)
    print(f"report: {out.run_dir / 'report.md'}", file=sys.stderr)
    print(f"console: {out.run_dir / 'report.html'}", file=sys.stderr)
    print(out.run_dir)
    return EXIT_OK if m.status is RunStatus.COMPLETED else EXIT_RUN_FAILED


def _cmd_pilot(args: argparse.Namespace) -> int:
    from blackgrid.pilot import run_pilot

    print("mock pilot: 8 dev cases x 2 conditions (first run computes experiments; later runs use the cache)...",
          file=sys.stderr)
    pilot_dir = run_pilot(args.runs_dir, None if args.no_cache else args.cache_dir)
    summary = json.loads((pilot_dir / "pilot.json").read_text(encoding="utf-8"))["summary"]
    for condition, row in summary.items():
        print(f"{condition:10} useful {row['useful_coverage']}  unsupported claims {row['unsupported_claim_rate']}  "
              f"failed {row['failed']}", file=sys.stderr)
    print(f"console: {pilot_dir / 'pilot.html'}", file=sys.stderr)
    print(pilot_dir)
    return EXIT_OK


def _cmd_ui(args: argparse.Namespace) -> int:
    from blackgrid.ui import write_index, write_pilot_page, write_run_page

    args.runs_dir.mkdir(parents=True, exist_ok=True)
    for d in sorted(p for p in args.runs_dir.iterdir() if p.is_dir()):
        if (d / "pilot.json").is_file():
            for sub in d.iterdir():
                if (sub / "investigation.json").is_file():
                    write_run_page(sub)
            write_pilot_page(d)
        elif (d / "investigation.json").is_file():
            write_run_page(d)
    index = write_index(args.runs_dir)
    print(index)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blackgrid", description="BLACKGRID bounded investigations.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a run configuration")
    validate.add_argument("config", type=Path)
    validate.set_defaults(func=_cmd_validate)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "runs")
    common.add_argument("--cache-dir", type=Path, default=REPO_ROOT / "runs" / "cache")
    common.add_argument("--no-cache", action="store_true", help="recompute every deterministic tool result")

    run = sub.add_parser("run", parents=[common], help="run the CollegeMsg investigation")
    run.add_argument("config", type=Path)
    run.add_argument("--data-root", type=Path, default=REPO_ROOT, help="base for the config's relative dataset path")
    run.add_argument("--mode", choices=["mock", "live", "replay"])
    run.add_argument("--condition", choices=["validated", "tool_only"])
    run.add_argument("--allow-paid", action="store_true", help="authorize paid LLM calls for this invocation")
    run.add_argument("--replay-from", type=Path, help="run directory whose llm_trace.jsonl to replay")
    run.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    run.set_defaults(func=_cmd_run)

    pilot = sub.add_parser("pilot", parents=[common], help="mock pilot on the dev benchmark")
    pilot.set_defaults(func=_cmd_pilot)

    ui = sub.add_parser("ui", parents=[common], help="rebuild HTML console pages")
    ui.set_defaults(func=_cmd_ui)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
