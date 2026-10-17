"""Offline command-line entry point.

    blackgrid validate CONFIG      validate a run configuration and print its hash
    blackgrid run CONFIG           execute an investigation (offline; mock mode by default)

Sprint 1 Day 5: `run` loads and projects the window, then runs the frozen community-vs-null
experiment and records its report. The investigation still ends FAILED (`not_implemented`)
because sensitivity, critic, and report stages do not exist yet. Window or experiment
abstentions are recorded as ABSTAINED. Any non-completed run exits with code 2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from blackgrid import __version__
from blackgrid.collegemsg import BoundedGraph, DataIntegrityError, build_bounded_graph
from blackgrid.experiment import DeadlineExceeded, run_community_test
from blackgrid.contracts import (
    CostRecord,
    Environment,
    Outcome,
    RunConfig,
    RunManifest,
    RunStatus,
    ToolCallRecord,
    canonical_sha256,
)

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_RUN_FAILED = 2

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_config(path: Path) -> RunConfig:
    return RunConfig.model_validate_json(path.read_text(encoding="utf-8"))


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, timeout=10, check=True
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


def _write_json(path: Path, payload: object) -> str:
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    path.write_bytes(data)  # bytes, so the hash matches the file on every platform
    return hashlib.sha256(data).hexdigest()


def capture_environment() -> Environment:
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    return Environment(
        python=platform.python_version(),
        platform=platform.platform(),
        blackgrid_version=__version__,
        dependency_lock_sha256=_file_sha256(REPO_ROOT / "uv.lock"),
        source_commit=commit or None,
        source_dirty=None if status is None else bool(status),
    )


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except (OSError, ValidationError, ValueError) as exc:
        print(f"invalid config: {exc}", file=sys.stderr)
        return EXIT_INVALID
    print(f"valid  protocol={config.protocol_version}  mode={config.mode}  sha256={canonical_sha256(config)}")
    return EXIT_OK


def _run_experiment(config: RunConfig, built: BoundedGraph, run_dir: Path, artifacts: dict[str, str],
                    calls: list[ToolCallRecord]) -> tuple[RunStatus, str]:
    spec = config.experiment
    if spec is None:
        return RunStatus.FAILED, "not_configured: no frozen experiment specification in the config"
    if spec.graph_id != built.record.graph_id:
        return RunStatus.FAILED, f"spec_mismatch: spec targets {spec.graph_id!r}, graph is {built.record.graph_id!r}"
    clock = time.perf_counter()
    try:
        report = run_community_test(built.graph, spec, spec_sha256=canonical_sha256(spec))
    except (DeadlineExceeded, ValueError) as exc:
        calls.append(ToolCallRecord(tool="experiment.run_community_test", args_sha256=canonical_sha256(spec),
                                    outcome=Outcome.FAILED, elapsed_s=round(time.perf_counter() - clock, 6),
                                    error=f"{type(exc).__name__}: {exc}"))
        return RunStatus.FAILED, f"experiment_failed: {type(exc).__name__}"
    abstained = report.verdict == "abstain"
    calls.append(ToolCallRecord(tool="experiment.run_community_test", args_sha256=canonical_sha256(spec),
                                outcome=Outcome.ABSTAINED if abstained else Outcome.COMPLETED,
                                elapsed_s=round(time.perf_counter() - clock, 6)))
    artifacts["experiment_report.json"] = _write_json(run_dir / "experiment_report.json", report.model_dump(mode="json"))
    if abstained:
        return RunStatus.ABSTAINED, "experiment_abstained: " + "; ".join(report.primary.unsuitable_reasons)
    return RunStatus.FAILED, (f"not_implemented: experiment verdict '{report.verdict}' recorded; missing-edge "
                              "sensitivity (Day 6), critic and report (Days 9-10) are not built yet")


def _cmd_run(args: argparse.Namespace) -> int:
    try:
        config = load_config(args.config)
    except (OSError, ValidationError, ValueError) as exc:
        print(f"invalid config: {exc}", file=sys.stderr)
        return EXIT_INVALID

    started = datetime.now(UTC)
    run_id = f"{started:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = args.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    artifacts: dict[str, str] = {"config.json": _write_json(run_dir / "config.json", config.model_dump(mode="json"))}

    calls: list[ToolCallRecord] = []
    clock = time.perf_counter()
    error: str | None = None
    built = None
    try:
        built = build_bounded_graph(args.data_root, config.dataset, config.window)
    except (DataIntegrityError, ValidationError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    load_outcome = (Outcome.COMPLETED if isinstance(built, BoundedGraph)
                    else Outcome.ABSTAINED if built is not None else Outcome.FAILED)
    calls.append(ToolCallRecord(tool="collegemsg.build_bounded_graph", args_sha256=canonical_sha256(config.window),
                                outcome=load_outcome, elapsed_s=round(time.perf_counter() - clock, 6), error=error))

    if isinstance(built, BoundedGraph):
        artifacts["input_profile.json"] = _write_json(run_dir / "input_profile.json", built.table.summary())
        artifacts["window_selection.json"] = _write_json(run_dir / "window_selection.json", built.selection.summary())
        artifacts["graph_record.json"] = _write_json(run_dir / "graph_record.json", built.record.model_dump(mode="json"))
        status, reason = _run_experiment(config, built, run_dir, artifacts, calls)
    elif built is not None:  # the window rule abstained
        artifacts["window_selection.json"] = _write_json(run_dir / "window_selection.json", built.summary())
        status, reason = RunStatus.ABSTAINED, f"window_abstention: {built.abstention_reason}"
    else:
        status, reason = RunStatus.FAILED, f"load_failed: {error}"

    manifest = RunManifest(
        run_id=run_id,
        created_utc=started,
        finished_utc=datetime.now(UTC),
        status=status,
        failure_reason=reason,
        config_sha256=canonical_sha256(config),
        environment=capture_environment(),
        input_hashes={config.dataset.dataset_id: config.dataset.sha256},
        seeds={"experiment_master": config.experiment.seed} if config.experiment else {},
        tool_calls=tuple(calls),
        cost=CostRecord(mode=config.mode),
        artifacts=artifacts,
    )
    (run_dir / "manifest.json").write_bytes(manifest.model_dump_json(indent=2).encode("utf-8"))
    print(f"run {run_id}: {manifest.status} ({manifest.failure_reason})", file=sys.stderr)
    print(run_dir)
    return EXIT_RUN_FAILED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blackgrid", description="Offline BLACKGRID investigations.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a run configuration")
    validate.add_argument("config", type=Path)
    validate.set_defaults(func=_cmd_validate)

    run = sub.add_parser("run", help="run an investigation offline")
    run.add_argument("config", type=Path)
    run.add_argument("--runs-dir", type=Path, default=REPO_ROOT / "runs")
    run.add_argument("--data-root", type=Path, default=REPO_ROOT, help="base for the config's relative dataset path")
    run.set_defaults(func=_cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
