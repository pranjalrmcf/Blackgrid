"""Fail-closed release evidence checks. Does not deploy, mutate state or call a provider."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def junit(path: Path, *, private_data: bool = False) -> dict[str, int]:
    cases = list(ET.parse(path).getroot().iter("testcase"))
    failed = sum(
        c.find("failure") is not None or c.find("error") is not None for c in cases
    )
    skipped = [c for c in cases if c.find("skipped") is not None]
    require(len(cases) >= 675, "Regression collection is incomplete")
    require(failed == 0, "Regression contains failures")
    # Match the documented private-data skips by their explicit reason, never arbitrary skips.
    allowed = {
        ("tests.test_collegemsg", "test_real_file_matches_published_counts"),
        ("tests.test_full_scope", "test_real_full_graph_matches_the_ingestion_counts"),
    }
    for case in skipped:
        marker = case.find("skipped")
        require(marker is not None, "Missing skip reason")
        require(
            (case.attrib.get("classname"), case.attrib.get("name")) in allowed,
            "Unexpected skipped check",
        )
    require(len(skipped) <= (0 if private_data else 2), "Too many skipped checks")
    return {
        "collected": len(cases),
        "passed": len(cases) - failed - len(skipped),
        "skipped": len(skipped),
    }


def security(scan: dict[str, Any], scope: str, *, now: float) -> dict[str, Any]:
    from datetime import datetime

    require(scope in ("local-restricted", "public"), "Unknown release scope")
    require(bool(scan.get("Results")), "Missing scanner coverage")
    kinds = {item.get("Type") for item in scan["Results"]}
    require(
        "debian" in kinds and "python-pkg" in kinds, "OS/Python coverage is required"
    )
    created = datetime.fromisoformat(
        scan["CreatedAt"].replace("Z", "+00:00")
    ).timestamp()
    require(0 <= now - created <= 86400, "Image scan is stale or from the future")
    findings = [v for item in scan["Results"] for v in item.get("Vulnerabilities", [])]
    critical = sum(v["Severity"] == "CRITICAL" for v in findings)
    high = sum(v["Severity"] == "HIGH" for v in findings)
    fixable_high = sum(
        v["Severity"] == "HIGH" and bool(v.get("FixedVersion")) for v in findings
    )
    require(
        critical == 0 and fixable_high == 0,
        "Critical or fixable high vulnerability blocks release",
    )
    require(scope != "public" or high == 0, "High findings block public release")
    return {
        "scope": scope,
        "critical": critical,
        "high": high,
        "fixable_high": fixable_high,
    }


def evidence(folder: Path, image_id: str, scope: str, *, now: float) -> dict[str, Any]:
    tests = junit(folder / "regression.xml")
    scan = json.loads((folder / "evidence/scan_phase9.json").read_bytes())
    summary = json.loads((folder / "evidence/scan_summary.json").read_bytes())
    require(summary["image_id"] == image_id, "Scanned image differs from release image")
    from datetime import datetime

    updated = datetime.fromisoformat(
        summary["scanner"]["VulnerabilityDB"]["UpdatedAt"].replace("Z", "+00:00")
    ).timestamp()
    require(
        0 <= now - updated <= 172800,
        "Vulnerability database is stale or from the future",
    )
    require(
        summary["scanner_digest"]
        == "aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222",
        "Unreviewed scanner identity",
    )
    require(
        summary["scan_sha256"]
        == hashlib.sha256(
            (folder / "evidence/scan_phase9.json").read_bytes()
        ).hexdigest(),
        "Scan evidence hash mismatch",
    )
    report = security(scan, scope, now=now)
    restored = json.loads((folder / "evidence/restore_drill.json").read_bytes())
    require(
        restored["scientific_api_result_exact"]
        and restored["all_job_columns_exact"]
        and restored["owner_denied"]
        and restored["idempotent_replay_exact"]
        and restored["actual_usd"] == 0
        and restored["real_provider_calls"] == 0,
        "Recovery verification incomplete",
    )
    staging = json.loads((folder / "evidence/staging.json").read_bytes())
    require(
        staging["monitoring"] and staging["alerts"] and staging["schema_reopen_exact"],
        "Staging gate failed",
    )
    return {
        "tests": tests,
        "security": report,
        "recovery": "passed",
        "staging": "passed",
    }


def quality() -> None:
    commands = [
        [
            "ruff",
            "check",
            "--no-cache",
            "--config",
            "scripts/ci/ruff.toml",
            "src",
            "tests",
            "scripts",
            "benchmarks",
        ],
        [
            "ruff",
            "format",
            "--check",
            "--no-cache",
            "scripts/release_gate.py",
            "scripts/verify_phase9.py",
            "tests/test_phase9.py",
        ],
        ["mypy", "--config-file", "scripts/ci/mypy.ini"],
    ]
    for command in commands:
        subprocess.run([sys.executable, "-m", *command], check=True, timeout=120)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("quality", "junit", "assess"))
    parser.add_argument("--folder", type=Path, default=Path("docs/production_phase9"))
    parser.add_argument("--image-id")
    parser.add_argument(
        "--scope", choices=("local-restricted", "public"), default="local-restricted"
    )
    args = parser.parse_args()
    if args.command == "quality":
        quality()
    elif args.command == "junit":
        print(json.dumps(junit(args.folder / "regression.xml")))
    else:
        import time

        require(bool(args.image_id), "An immutable image ID is required")
        print(
            json.dumps(
                evidence(args.folder, args.image_id, args.scope, now=time.time()),
                indent=2,
            )
        )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        KeyError,
        OSError,
        ET.ParseError,
        subprocess.SubprocessError,
    ) as error:
        print(f"Release check failed: {type(error).__name__}", file=sys.stderr)
        raise SystemExit(2) from None
