"""Command-line entry point.

    blackgrid validate CONFIG                 validate a run configuration and print its hash
    blackgrid run CONFIG [options]            start a CollegeMsg investigation (mock mode by default)
    blackgrid status [RUN_ID]                 list runs, or show one run's stage, analyses, limits, pause
    blackgrid resume RUN_ID [--allow-paid]    continue a paused or interrupted run where it stopped
    blackgrid cancel RUN_ID                   stop a run at its next safe boundary
    blackgrid deny RUN_ID                     refuse a pending paid-execution authorization
    blackgrid reconcile RUN_ID --retry|--stop resolve an uncertain paid call (never auto-resent)
    blackgrid pilot                           mock pilot: tool_only vs validated on 8 dev cases
    blackgrid ui                              rebuild the HTML console pages and runs/index.html

`run` options:
    --mode mock|live|replay    override the config's mode
    --condition validated|tool_only
    --allow-paid               authorize paid calls for this run (live mode also needs
                               paid_execution_authorized=true); without it a live run pauses
                               before its first paid call
    --replay-from RUN_DIR      replay the recorded LLM responses of an earlier run
    --parent RUN_ID            record that this run deliberately changes an earlier one
    --no-cache                 recompute every tool result

Exit codes: 0 completed, 1 invalid input or not authorized, 2 run did not complete
(partial, abstained, failed, cancelled, denied, or budget exhausted), 3 paused (resumable).
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
from blackgrid.collegemsg import BoundedGraph, DataIntegrityError, build_graph
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
from blackgrid.runner import (
    REPO_ROOT,
    LiveNotAuthorized,
    apply_env_model,
    capture_environment,
    make_provider,
    resume_investigation,
    run_investigation,
    write_json,
)
from blackgrid.workflow.api import open_services
from blackgrid.workflow.api import status as workflow_status
from blackgrid.workflow.engine import ResumeBlocked
from blackgrid.workflow.store import RunLocked, StoreError

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_RUN_FAILED = 2
EXIT_PAUSED = 3


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
        overrides = {k: v for k, v in (("mode", args.mode), ("condition", args.condition),
                                     ("investigation_family", args.family), ("question", args.question),
                                     ("planning_mode", args.planning_mode)) if v}
        if overrides:
            config = RunConfig.model_validate(config.model_dump(mode="json") | overrides)
        config = apply_env_model(config, args.env_file)
        if args.live_allowance:
            from blackgrid.live_allowance import constrain
            if config.mode.value != "live" or not args.allow_paid:
                raise ValueError("a live allowance requires live mode and --allow-paid")
            config = constrain(config, args.live_allowance, args.runs_dir)
    except (OSError, ValidationError, ValueError) as exc:
        print(f"invalid config: {exc}", file=sys.stderr)
        return EXIT_INVALID
    if config.experiment is None:
        print("invalid config: no frozen experiment specification", file=sys.stderr)
        return EXIT_INVALID

    provider = None  # created lazily by the workflow, after authorization
    try:
        if config.mode.value == "live" and not config.paid_execution_authorized:
            raise LiveNotAuthorized("live mode needs paid_execution_authorized=true in the config")
        if config.mode.value == "replay" and args.replay_from is None:
            raise LiveNotAuthorized("replay mode needs --replay-from RUN_DIR")
        if config.mode.value == "live" and args.allow_paid:
            provider = make_provider(config, allow_paid=True, replay_from=None, env_file=args.env_file)
            pricing = provider.pricing()  # confirm current pricing before anything else
            print(f"live mode: {pricing.model} at ${pricing.prompt_usd_per_token * 1e6:.4f}/M input, "
                  f"${pricing.completion_usd_per_token * 1e6:.4f}/M output tokens; caps: "
                  f"{config.budget.max_llm_calls} calls, {config.budget.max_tokens} tokens, "
                  f"${config.budget.max_usd_per_investigation} per run, ${config.budget.max_usd_current_sprint} "
                  f"this sprint, ${config.budget.max_usd_total} project", file=sys.stderr)
    except (LiveNotAuthorized, PricingUnavailable, OSError) as exc:
        print(f"not started: {exc}", file=sys.stderr)
        return EXIT_INVALID

    clock = time.perf_counter()
    try:
        built = build_graph(args.data_root, config)  # frozen first window, or the full dataset
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

    inp = InvestigationInput(case_id=built.record.graph_id, question=config.question,
                             request={"method": "auto", "family": config.investigation_family,
                                      "planning_mode": config.planning_mode},
                             graph=built.graph, record=built.record, spec=config.experiment)
    reproduce = f"uv run --frozen blackgrid run {args.config.as_posix()} --mode {config.mode.value}"
    scope = ("FULL DATASET (exp-v2-full, exploratory): "
             f"{built.record.window_events:,} events, {built.record.active_nodes:,} people, "
             f"{built.record.unique_edges:,} connections; first run takes about 12 minutes"
             if config.scope == "full_dataset" else
             "first-week window (preregistered exp-v1.1); first run takes about 2 minutes")
    if config.investigation_family != "community":
        scope = f"{config.scope}, exploratory structural investigation; no community significance claim"
    print(f"running {config.condition} investigation in {config.mode.value} mode on the {scope}...",
          file=sys.stderr)
    try:
        out = run_investigation(
            inp, config, provider, args.runs_dir, cache_dir=None if args.no_cache else args.cache_dir,
            input_ref={"kind": "collegemsg", "data_root": str(args.data_root.resolve())}, reproduce=reproduce,
            extra_artifacts={"input_profile.json": built.table.summary(),
                             built.scope_artifact: built.scope_summary()},
            allow_paid=args.allow_paid, replay_from=args.replay_from, env_file=args.env_file, parent_run=args.parent)
    except RunLocked as exc:
        print(f"not started: {exc}", file=sys.stderr)
        return EXIT_INVALID
    return _report(out)


def _report(out) -> int:
    """Print a run's outcome and choose the exit code."""
    o = out.outcome
    if o.status == "paused":
        print(f"run {o.run_id}: PAUSED · {o.reason}", file=sys.stderr)
        print(f"  resume:  uv run --frozen blackgrid resume {o.run_id}"
              + (" --allow-paid" if (o.pause or {}).get("kind") == "authorization" else ""), file=sys.stderr)
        if (o.pause or {}).get("kind") == "authorization":
            print(f"  deny:    uv run --frozen blackgrid deny {o.run_id}", file=sys.stderr)
        if (o.pause or {}).get("kind") == "reconciliation":
            print(f"  reconcile: uv run --frozen blackgrid reconcile {o.run_id} --retry   (or --stop)", file=sys.stderr)
        print(out.run_dir)
        return EXIT_PAUSED
    m = out.manifest
    if m is None:  # finished without a manifest (e.g. failed before finalization could load inputs)
        print(f"run {o.run_id}: {o.status} · {o.reason}", file=sys.stderr)
        print(out.run_dir)
        return EXIT_RUN_FAILED
    print(f"run {m.run_id}: {m.status.value} · verdict {out.result.verdict} · "
          f"LLM calls {m.cost.llm_calls} · cost ${m.cost.actual_usd:.4f}"
          + (f" · {m.failure_reason}" if m.failure_reason else ""), file=sys.stderr)
    print(f"report: {out.run_dir / 'report.md'}", file=sys.stderr)
    print(f"console: {out.run_dir / 'report.html'}", file=sys.stderr)
    print(out.run_dir)
    return EXIT_OK if m.status is RunStatus.COMPLETED else EXIT_RUN_FAILED


def _cmd_resume(args: argparse.Namespace) -> int:
    decision = None
    if getattr(args, "decision", None):
        decision = {"decision": args.decision}
    try:
        out = resume_investigation(args.run_id, args.runs_dir, decision=decision, allow_paid=args.allow_paid,
                                   force_unlock=args.force_unlock,
                                   cache_dir=None if args.no_cache else args.cache_dir, env_file=args.env_file)
    except (RunLocked, ResumeBlocked, StoreError, OSError) as exc:
        print(f"cannot resume: {exc}", file=sys.stderr)
        return EXIT_INVALID
    return _report(out)


def _cmd_cancel(args: argparse.Namespace) -> int:
    services = open_services(args.runs_dir)
    try:
        services.store.request_cancel(args.run_id)
        row = services.store.run(args.run_id)
        locked, paused = bool(row["lock_owner"]), row["status"] == "paused"
    except StoreError as exc:
        print(f"cannot cancel: {exc}", file=sys.stderr)
        return EXIT_INVALID
    finally:
        services.close()
    if locked:
        print(f"cancellation requested; the running worker stops at its next safe boundary", file=sys.stderr)
        return EXIT_OK
    args.decision = "cancel" if paused else None
    args.allow_paid, args.force_unlock = False, False
    return _cmd_resume(args)  # finalizes as cancelled at the next node boundary


def _cmd_deny(args: argparse.Namespace) -> int:
    args.decision, args.allow_paid, args.force_unlock = "deny", False, False
    return _cmd_resume(args)


def _cmd_reconcile(args: argparse.Namespace) -> int:
    args.decision = "retry" if args.retry else "stop"
    args.allow_paid, args.force_unlock = False, False
    return _cmd_resume(args)


def _cmd_console(args: argparse.Namespace) -> int:
    from blackgrid.console.server import Console, serve

    args.runs_dir.mkdir(parents=True, exist_ok=True)
    allowance = None
    if args.allow_paid:
        from blackgrid.live_allowance import ensure_allowance
        allowance = ensure_allowance(args.runs_dir)
    console = Console(args.runs_dir, args.cache_dir, args.config, args.data_root, args.port, live_allowance=allowance)
    try:
        httpd = serve(console)
    except OSError as exc:
        print(f"cannot start the console on 127.0.0.1:{args.port}: {exc}", file=sys.stderr)
        return EXIT_INVALID
    print(f"BLACKGRID console: http://127.0.0.1:{args.port}/  (local only; Ctrl+C to stop)", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return EXIT_OK


def _cmd_status(args: argparse.Namespace) -> int:
    services = open_services(args.runs_dir)
    try:
        if not args.run_id:
            rows = services.store.runs()
            for row in rows[: args.limit]:
                print(f"{row['run_id']:42} {row['status']:16} stage={row['stage'] or '-':15} "
                      f"{(row['status_reason'] or '')[:70]}")
            return EXIT_OK
        info = workflow_status(services, args.run_id)
    except StoreError as exc:
        print(f"unknown run: {exc}", file=sys.stderr)
        return EXIT_INVALID
    finally:
        services.close()
    if args.json:
        print(json.dumps(info, indent=2))
        return EXIT_OK
    remaining = info.get("remaining") or {}
    print(f"run       {info['run_id']}\nstatus    {info['status']}" + (f"  ({info['reason']})" if info.get("reason")
                                                                       else "")
          + f"\nstage     {info.get('stage')}\nrequired  {', '.join(info.get('required') or []) or '-'}"
          f"\ncompleted {', '.join(info.get('completed') or []) or '-'}"
          f"\nmissing   {', '.join(info.get('missing') or []) or '-'}"
          f"\nremaining calls={remaining.get('llm_calls')} tokens={remaining.get('tokens')} "
          f"usd_this_run={remaining.get('usd_this_run')} revisions={remaining.get('revisions')}"
          + (f"\npause     {info['pause'].get('kind')}: {info['pause'].get('reason')}" if info.get("pause") else "")
          + ("\nlocked    yes (a worker is active)" if info.get("locked") else ""))
    return EXIT_OK


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


def _cmd_ingest(args: argparse.Namespace) -> int:
    from blackgrid.ingestion import ingest_full, write_ingestion

    try:
        config = load_config(args.config)
        if args.output.exists():
            raise ValueError("output already exists; choose a fresh directory")
        report = ingest_full(args.data_root, config.dataset)
        write_ingestion(report, args.output)
    except (OSError, ValidationError, ValueError, DataIntegrityError) as exc:
        print(f"ingestion failed: {exc}", file=sys.stderr)
        return EXIT_INVALID
    counts = report["validation"]
    print(f"full CollegeMsg: {counts['valid_events']} events, "
          f"{counts['active_nodes']} nodes, {counts['unique_undirected_pairs']} undirected pairs")
    print(args.output.resolve())
    return EXIT_OK


def _cmd_sprint3(args: argparse.Namespace) -> int:
    from blackgrid.sprint3 import run_suite

    if not args.output.resolve().is_relative_to((REPO_ROOT / "runs").resolve()):
        print("Sprint 3 output must be under runs/ to protect evaluator-private artifacts", file=sys.stderr)
        return EXIT_INVALID
    try:
        folder = run_suite(args.output, args.protocol)
        status = json.loads((folder / "suite.json").read_text(encoding="utf-8"))["status"]
    except (OSError, ValueError) as exc:
        print(f"Sprint 3 failed: {exc}", file=sys.stderr)
        return EXIT_INVALID
    print(f"Sprint 3 {status}: {folder}")
    return EXIT_OK if status == "completed" else EXIT_RUN_FAILED


def _cmd_sprint3_verify(args: argparse.Namespace) -> int:
    from blackgrid.sprint3 import verify_suite

    try:
        print(json.dumps(verify_suite(args.output), sort_keys=True))
    except (OSError, ValueError, KeyError) as exc:
        print(f"Sprint 3 verification failed: {exc}", file=sys.stderr)
        return EXIT_INVALID
    return EXIT_OK


def _cmd_sprint4(args: argparse.Namespace) -> int:
    from blackgrid.sprint4 import export_summary, run_suite

    if not args.output.resolve().is_relative_to((REPO_ROOT / "runs").resolve()):
        print("Sprint 4 output must be under runs/ to protect evaluator-private artifacts", file=sys.stderr)
        return EXIT_INVALID
    try:
        folder = run_suite(args.output, args.protocol)
        status = json.loads((folder / "suite.json").read_text(encoding="utf-8"))["status"]
        if (folder / "evaluation.json").is_file():
            export_summary(folder, REPO_ROOT / "results" / f"sprint04-{folder.name}")
    except (OSError, ValueError) as exc:
        print(f"Sprint 4 failed: {exc}", file=sys.stderr)
        return EXIT_INVALID
    print(f"Sprint 4 {status}: {folder}")
    return EXIT_OK if status == "completed" else EXIT_RUN_FAILED


def _cmd_sprint4_live(args: argparse.Namespace) -> int:
    from blackgrid.sprint4_live import export_summary, run_pilot

    if not args.allow_paid:
        print("the live pilot makes paid calls; add --allow-paid to authorize this one execution", file=sys.stderr)
        return EXIT_INVALID
    if not args.output.resolve().is_relative_to((REPO_ROOT / "runs").resolve()):
        print("pilot output must be under runs/", file=sys.stderr)
        return EXIT_INVALID
    try:
        folder = run_pilot(args.output, cap_usd=args.max_usd, allow_paid=True)
        suite = json.loads((folder / "suite.json").read_text(encoding="utf-8"))
        if (folder / "evaluation.json").is_file():
            export_summary(folder, REPO_ROOT / "results" / f"sprint04-{folder.name}")
    except (OSError, ValueError, PermissionError) as exc:
        print(f"live pilot failed: {exc}", file=sys.stderr)
        return EXIT_INVALID
    print(f"live pilot {suite['status']}: USD {suite['pilot_usd']:.4f} of {suite['pilot_cap_usd']:.2f}; {folder}")
    return EXIT_OK if suite["status"] == "completed" else EXIT_RUN_FAILED


def _cmd_predict_eval(args: argparse.Namespace) -> int:
    """Sprint 6: run the frozen prediction-v1 evaluation on CollegeMsg (local, offline, USD 0)."""
    from blackgrid.collegemsg import load_events
    from blackgrid.prediction.suite import run

    if not args.output.resolve().is_relative_to((REPO_ROOT / "runs").resolve()):
        print("prediction output must be under runs/ (pair-level artifacts stay local)", file=sys.stderr)
        return EXIT_INVALID
    config = load_config(args.config)
    table = load_events(args.data_root / config.dataset.path, config.dataset.sha256)
    folder = run(list(table.events), args.output, protocol_path=REPO_ROOT / "protocols" / "sprint06_prediction_v1.md",
                 data_sha256=table.sha256)
    print(f"prediction-v1 completed: {folder}")
    return EXIT_OK


def _cmd_forecast(args: argparse.Namespace) -> int:
    """Sprint 6: prospective known-node forecast from a frozen prediction-v1 evaluation (mock, USD 0)."""
    from datetime import UTC, datetime

    from blackgrid.collegemsg import load_events
    from blackgrid.console.render import write_forecast_snapshot, write_index_snapshot
    from blackgrid.prediction.service import PredictionToolRejected, forecast

    config = load_config(args.config)
    table = load_events(args.data_root / config.dataset.path, config.dataset.sha256)
    out = args.runs_dir / f"forecast-{args.task}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    try:
        folder = forecast(list(table.events), args.evaluation, out, args.task, args.method, data_sha256=table.sha256)
    except PredictionToolRejected as exc:
        print(f"forecast rejected: {exc}", file=sys.stderr)
        return EXIT_INVALID
    write_forecast_snapshot(args.runs_dir, folder)
    write_index_snapshot(args.runs_dir)
    print(f"forecast: {folder / 'forecast.html'}")
    return EXIT_OK


def _cmd_predict_rolling(args: argparse.Namespace) -> int:
    """prediction-v2: frozen rolling-origin evaluation (local, offline, USD 0; development evidence)."""
    from blackgrid.collegemsg import load_events
    from blackgrid.prediction.rolling import run

    if not args.output.resolve().is_relative_to((REPO_ROOT / "runs").resolve()):
        print("prediction output must be under runs/", file=sys.stderr)
        return EXIT_INVALID
    config = load_config(args.config)
    table = load_events(args.data_root / config.dataset.path, config.dataset.sha256)
    folder = run(list(table.events), args.output, protocol_path=REPO_ROOT / "protocols" / "sprint06_prediction_v2.md",
                 data_sha256=table.sha256)
    print(f"prediction-v2 completed: {folder}")
    return EXIT_OK


def _cmd_predict_confirm(args: argparse.Namespace) -> int:
    """prediction-v3: frozen confirmation of logistic_v2 on an authorized second dataset (local, USD 0)."""
    from blackgrid.datasets import load
    from blackgrid.prediction.rolling import run

    if not args.output.resolve().is_relative_to((REPO_ROOT / "runs").resolve()):
        print("prediction output must be under runs/", file=sys.stderr)
        return EXIT_INVALID
    data = load(args.dataset, args.data_root)
    folder = run(data.events, args.output, protocol_path=REPO_ROOT / "protocols" / "sprint06_prediction_v3_bitcoin.md",
                 data_sha256=data.sha256, version="prediction-v3", primary="logistic_v2", active_window_bins=1,
                 note=f"confirmatory test of H1 on unseen data ({args.dataset})")
    (folder / "dataset_profile.json").write_text(json.dumps(data.profile, indent=2, sort_keys=True), encoding="utf-8")
    print(f"prediction-v3 completed: {folder}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blackgrid", description="BLACKGRID bounded investigations.")
    sub = parser.add_subparsers(dest="command", required=True)
    def sprint5_run(args):
        from blackgrid.sprint5 import run_suite
        try:
            summary = run_suite(args.output)
        except (OSError, ValueError, TimeoutError) as exc:
            print(f"Sprint 5 evaluation failed: {exc}", file=sys.stderr)
            return EXIT_RUN_FAILED
        print(json.dumps(summary, indent=2))
        return EXIT_OK if all(r["useful"] == 16 for r in summary["arms"].values()) else EXIT_RUN_FAILED
    sprint5 = sub.add_parser("sprint5", help="run frozen offline structural-tool and planning evaluation")
    sprint5.add_argument("--output", type=Path, required=True)
    sprint5.set_defaults(func=sprint5_run)
    def live5_run(args):
        from blackgrid.sprint5_live import run_pilot
        try:
            summary = run_pilot(args.output, allow_paid=args.allow_paid)
        except (OSError, ValueError, PermissionError) as exc:
            print(f"Live pilot not completed: {exc}", file=sys.stderr)
            return EXIT_RUN_FAILED
        print(json.dumps(summary, indent=2))
        return EXIT_OK if summary["status"] == "completed" else EXIT_RUN_FAILED
    live5 = sub.add_parser("sprint5-live", help="small authorized real-model pilot using retained USD 0.50 allowance")
    live5.add_argument("--output", type=Path, required=True)
    live5.add_argument("--allow-paid", action="store_true")
    live5.set_defaults(func=live5_run)

    sprint3 = sub.add_parser("sprint3", help="run the frozen offline validation and method comparison")
    sprint3.add_argument("--output", type=Path, required=True, help="fresh directory under runs/")
    sprint3.set_defaults(func=_cmd_sprint3)
    verify3 = sub.add_parser("sprint3-verify", help="verify saved Sprint 3 artifacts and independent scores")
    verify3.add_argument("output", type=Path)
    verify3.set_defaults(func=_cmd_sprint3_verify)
    sprint4 = sub.add_parser("sprint4", help="run the frozen Sprint 4 fresh evaluation (baseline, tool_only, validated)")
    sprint4.add_argument("--output", type=Path, required=True, help="fresh directory under runs/")
    sprint4.add_argument("--protocol", choices=("s4-v1", "s4-v2"), default="s4-v2",
                         help="frozen protocol; each has its own fresh case IDs")
    sprint4.set_defaults(func=_cmd_sprint4)
    predict = sub.add_parser("predict-eval", help="Sprint 6: frozen temporal link-prediction evaluation (local)")
    predict.add_argument("config", type=Path, help="a config naming the approved CollegeMsg file")
    predict.add_argument("--output", type=Path, required=True, help="fresh directory under runs/")
    predict.add_argument("--data-root", type=Path, default=REPO_ROOT)
    predict.set_defaults(func=_cmd_predict_eval)
    rolling_p = sub.add_parser("predict-rolling", help="prediction-v2 rolling-origin evaluation (local)")
    rolling_p.add_argument("config", type=Path)
    rolling_p.add_argument("--output", type=Path, required=True)
    rolling_p.add_argument("--data-root", type=Path, default=REPO_ROOT)
    rolling_p.set_defaults(func=_cmd_predict_rolling)
    confirm = sub.add_parser("predict-confirm", help="prediction-v3: confirm logistic_v2 on Bitcoin OTC (local)")
    confirm.add_argument("--dataset", choices=["snap-bitcoin-otc"], default="snap-bitcoin-otc")
    confirm.add_argument("--output", type=Path, required=True)
    confirm.add_argument("--data-root", type=Path, default=REPO_ROOT / "data")
    confirm.set_defaults(func=_cmd_predict_confirm)
    fc = sub.add_parser("forecast", help="Sprint 6: forecast connections from a frozen prediction-v1 evaluation")
    fc.add_argument("config", type=Path)
    fc.add_argument("--evaluation", type=Path, required=True, help="completed prediction-v1 folder, e.g. runs/sprint6-v1")
    fc.add_argument("--task", choices=("new_pair", "repeat_pair"), default="new_pair")
    fc.add_argument("--method", default="selected", help="'selected' (frozen choice) or a registered method name")
    fc.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "runs")
    fc.add_argument("--data-root", type=Path, default=REPO_ROOT)
    fc.set_defaults(func=_cmd_forecast)
    live4 = sub.add_parser("sprint4-live", help="run the frozen Sprint 4 live pilot (paid; needs --allow-paid)")
    live4.add_argument("--output", type=Path, required=True, help="fresh directory under runs/")
    live4.add_argument("--max-usd", type=float, default=0.50, help="total pilot cap in USD (at most 0.50)")
    live4.add_argument("--allow-paid", action="store_true", help="authorize this one paid execution")
    live4.set_defaults(func=_cmd_sprint4_live)

    ingest = sub.add_parser("ingest", help="validate and describe full CollegeMsg without running inference")
    ingest.add_argument("config", type=Path)
    ingest.add_argument("--data-root", type=Path, default=REPO_ROOT)
    ingest.add_argument("--output", type=Path, required=True, help="new directory for aggregate reports")
    ingest.set_defaults(func=_cmd_ingest)

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
    run.add_argument("--family", choices=["community", "centrality", "bridge", "forecast", "auto"], help="question-specific investigation")
    run.add_argument("--question", help="structural research question (treat as untrusted data)")
    run.add_argument("--planning-mode", choices=["adaptive", "single"], help="permit one follow-up or use one plan")
    run.add_argument("--condition", choices=["validated", "tool_only"])
    run.add_argument("--allow-paid", action="store_true", help="authorize paid LLM calls for this invocation")
    run.add_argument("--live-allowance", type=Path, help="retained console/trial allowance; never resets prior spend")
    run.add_argument("--replay-from", type=Path, help="run directory whose llm_trace.jsonl to replay")
    run.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    run.add_argument("--parent", help="run ID this run deliberately changes (recorded, never resumed into)")

    def run_id_command(name: str, func, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, parents=[common], help=help_text)
        p.add_argument("run_id")
        p.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
        p.set_defaults(func=func, decision=None, allow_paid=False, force_unlock=False)
        return p

    res = run_id_command("resume", _cmd_resume, "continue a paused or interrupted run")
    res.add_argument("--allow-paid", action="store_true", help="grant scoped paid-execution authorization")
    res.add_argument("--force-unlock", action="store_true",
                     help="take over a run whose previous worker crashed (only if it has really stopped)")
    run_id_command("cancel", _cmd_cancel, "cancel a run at its next safe boundary")
    run_id_command("deny", _cmd_deny, "refuse a pending paid-execution authorization")
    rec = run_id_command("reconcile", _cmd_reconcile, "resolve an uncertain paid call")
    choice = rec.add_mutually_exclusive_group(required=True)
    choice.add_argument("--retry", action="store_true",
                        help="keep the uncertain charge and retry once within the caps")
    choice.add_argument("--stop", action="store_true", help="keep the uncertain charge and stop the run")

    con = sub.add_parser("console", parents=[common], help="serve the interactive console on 127.0.0.1")
    con.add_argument("--port", type=int, default=8765)
    con.add_argument("--allow-paid", action="store_true", help="enable retained USD 0.50 live allowance; restarts do not renew it")
    con.add_argument("--config", type=Path, default=REPO_ROOT / "configs" / "collegemsg_sprint01.json",
                     help="config used by the console's 'Start mock run' action (always run in mock mode)")
    con.add_argument("--data-root", type=Path, default=REPO_ROOT)
    con.set_defaults(func=_cmd_console)

    st = sub.add_parser("status", parents=[common], help="list runs or show one run's progress")
    st.add_argument("run_id", nargs="?")
    st.add_argument("--json", action="store_true")
    st.add_argument("--limit", type=int, default=20)
    st.set_defaults(func=_cmd_status)
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
