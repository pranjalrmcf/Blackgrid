"""Offline command-line entry point.

    blackgrid validate CONFIG      validate a run configuration and print its hash
    blackgrid run CONFIG           execute an investigation (offline; mock mode by default)

Sprint 1 Day 3: `run` executes the load/window/projection stage, records its aggregate
artifacts, then stops with a FAILED manifest because the experiment stage (Day 5) does not exist
yet. A window abstention is recorded as ABSTAINED. Any non-completed run exits with code 2.
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

    clock = time.perf_counter()
    error: str | None = None
    built = None
    try:
        built = build_bounded_graph(args.data_root, config.dataset, config.window)
    except (DataIntegrityError, ValidationError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - clock

    if isinstance(built, BoundedGraph):
        artifacts["input_profile.json"] = _write_json(run_dir / "input_profile.json", built.table.summary())
        artifacts["window_selection.json"] = _write_json(run_dir / "window_selection.json", built.selection.summary())
        artifacts["graph_record.json"] = _write_json(run_dir / "graph_record.json", built.record.model_dump(mode="json"))
        status, reason, stage = RunStatus.FAILED, "not_implemented: experiment stage arrives on Day 5", Outcome.COMPLETED
    elif built is not None:  # the window rule abstained
        artifacts["window_selection.json"] = _write_json(run_dir / "window_selection.json", built.summary())
        status, reason, stage = RunStatus.ABSTAINED, f"window_abstention: {built.abstention_reason}", Outcome.ABSTAINED
    else:
        status, reason, stage = RunStatus.FAILED, f"load_failed: {error}", Outcome.FAILED

    manifest = RunManifest(
        run_id=run_id,
        created_utc=started,
        finished_utc=datetime.now(UTC),
        status=status,
        failure_reason=reason,
        config_sha256=canonical_sha256(config),
        environment=capture_environment(),
        input_hashes={config.dataset.dataset_id: config.dataset.sha256},
        tool_calls=(
            ToolCallRecord(
                tool="collegemsg.build_bounded_graph",
                args_sha256=canonical_sha256(config.window),
                outcome=stage,
                elapsed_s=round(elapsed, 6),
                error=error,
            ),
        ),
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
