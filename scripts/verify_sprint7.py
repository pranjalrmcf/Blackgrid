"""Clean source-copy reproduction using the offline environment prepared from uv.lock.

Usage: python scripts/verify_sprint7.py --python runs/sprint7-clean-env/Scripts/python.exe
Creates fresh source/results; never copies raw data, credentials or historical runs.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--name", default="sprint7-clean-source")
    args = parser.parse_args()
    if not args.name.replace("-", "").isalnum():
        raise ValueError("simple snapshot name required")
    target = ROOT / "runs" / args.name
    target.mkdir(exist_ok=False)
    for directory in ("src", "tests", "configs", "protocols"):
        shutil.copytree(ROOT / directory, target / directory, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for name in ("uv.lock", "pyproject.toml"):
        shutil.copy2(ROOT / name, target / name)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(target / "src")
    python = str(args.python.resolve())
    commands = [[python, "-m", "blackgrid", "sprint7", "--output", "runs/reproduction"],
                [python, "-m", "blackgrid", "sprint7", "--output", "runs/reproduction", "--replay"],
                [python, "-m", "pytest", "tests/test_sprint7.py", "tests/test_research_agent.py"]]
    records = []
    for command in commands:
        result = subprocess.run(command, cwd=target, env=env, capture_output=True, text=True, timeout=120)
        records.append({"command": command[1:], "returncode": result.returncode,
                        "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode:
            break
    reference = json.loads((ROOT / "results" / "sprint07-v1" / "scientific_hashes.json").read_text())
    comparisons = {}
    for name in ("summary.json", "beliefs.json", "decisions.json", "reliability.json", "causal.json"):
        actual = target / "runs" / "reproduction" / name
        comparisons[name] = actual.exists() and hashlib.sha256(actual.read_bytes()).hexdigest() == reference[name]
    report = {"commands": records, "scientific_artifacts_identical": comparisons,
              "passed": len(records) == 3 and all(r["returncode"] == 0 for r in records) and all(comparisons.values())}
    (target / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
