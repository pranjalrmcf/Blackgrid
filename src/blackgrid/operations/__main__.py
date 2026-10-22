"""Container entry point. Default service startup is offline and performs no analysis."""
from __future__ import annotations

import argparse
import json

from pydantic import ValidationError

from blackgrid.operations.health import alive, readiness
from blackgrid.operations.settings import load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "api", "health"))
    checks = parser.add_mutually_exclusive_group()
    checks.add_argument("--liveness", action="store_true")
    checks.add_argument("--readiness", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
    except ValidationError:
        print(json.dumps({"status": "unavailable", "failures": ["invalid_deployment_settings"]}))
        return 1
    if args.command == "health":
        failures = ([] if alive(settings) else ["server_unavailable"]) if args.liveness else readiness(settings)
        print(json.dumps({"status": "ready" if not failures else "unavailable", "failures": failures}))
        return int(bool(failures))
    try:
        settings.runs_dir.mkdir(parents=True, exist_ok=True)
        settings.cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        print(json.dumps({"status": "unavailable", "failures": ["state_unwritable"]}))
        return 1
    failures = readiness(settings, probe_server=False)
    if failures:
        print(json.dumps({"status": "unavailable", "failures": failures}))
        return 1
    if args.command == "api":
        try:
            from blackgrid.operations.api import launch
            return launch(settings)
        except (OSError, ValueError):
            print(json.dumps({"status": "unavailable", "failures": ["invalid_api_configuration"]}))
            return 1
    from blackgrid.cli import main as cli
    return cli(["console", "--config", str(settings.config), "--data-root", str(settings.data_root),
                "--runs-dir", str(settings.runs_dir), "--cache-dir", str(settings.cache_dir),
                "--port", str(settings.port), "--shutdown-grace-seconds", str(settings.shutdown_grace_seconds)])


if __name__ == "__main__":
    raise SystemExit(main())
