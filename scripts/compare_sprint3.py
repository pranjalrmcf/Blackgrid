"""Compare two frozen-suite executions without treating replay as new evidence.

Timings, run-directory names and token estimates vary; scientific scores must match.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

VOLATILE = {"elapsed_s", "optimizer_elapsed_s", "run_dir", "tokens"}


def strip(value):
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


def compare(a: Path, b: Path) -> dict:
    read = lambda folder, name: json.loads((folder / name).read_text(encoding="utf-8"))
    for folder in (a, b):
        assert read(folder, "suite.json")["status"] == "completed"
    assert read(a, "freeze.json")["source_hashes"] == read(b, "freeze.json")["source_hashes"]
    assert read(a, "freeze.json")["backend_versions"] == read(b, "freeze.json")["backend_versions"]
    assert read(a, "registry.json") == read(b, "registry.json")
    assert strip(read(a, "evaluation.json")) == strip(read(b, "evaluation.json"))
    assert strip(read(a, "method_summary.json")) == strip(read(b, "method_summary.json"))
    paths = sorted((a / "methods").glob("*.json"))
    assert len(paths) == len(list((b / "methods").glob("*.json"))) == 54
    for path in paths:
        assert strip(read(a, "methods/" + path.name)) == strip(read(b, "methods/" + path.name)), path.name
    return {"status": "matched", "case_conditions": 48, "method_graph_seeds": 54,
            "excluded_volatile_fields": sorted(VOLATILE),
            "note": "Same instances rerun; reproduction is not independent scientific evidence."}


if __name__ == "__main__":
    print(json.dumps(compare(Path(sys.argv[1]), Path(sys.argv[2])), sort_keys=True))
