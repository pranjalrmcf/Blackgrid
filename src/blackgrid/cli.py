"""Offline command-line entry point.

    blackgrid validate CONFIG      validate a run configuration and print its hash
    blackgrid run CONFIG           execute an investigation (offline; mock mode by default)

Sprint 1 Day 2: the pipeline stages are not implemented yet, so `run` validates the
configuration, records a FAILED run manifest stating why, and exits with code 2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from blackgrid import __version__
from blackgrid.contracts import CostRecord, Environment, RunConfig, RunManifest, RunStatus, canonical_sha256

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
    manifest = RunManifest(
        run_id=run_id,
        created_utc=started,
        finished_utc=datetime.now(UTC),
        status=RunStatus.FAILED,
        failure_reason="not_implemented: loader, window/projection, and experiment stages arrive on Days 3-5",
        config_sha256=canonical_sha256(config),
        environment=capture_environment(),
        input_hashes={config.dataset.dataset_id: config.dataset.sha256},
        cost=CostRecord(mode=config.mode),
    )

    run_dir = args.runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "config.json").write_text(config.model_dump_json(indent=2), encoding="utf-8")
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
    run.set_defaults(func=_cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
