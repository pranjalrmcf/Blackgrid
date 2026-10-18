"""Post-run audit: recompute saved scores, summaries and method arithmetic.

No tuning or result rewriting. Usage: python scripts/verify_sprint3.py RUN_DIRECTORY
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import networkx as nx

from blackgrid.evaluation import evaluate_run, summarize
from blackgrid.methods import validate_partition
from blackgrid.sprint3 import verify_suite
from blackgrid.validation import validation_input


def main(folder: Path) -> dict:
    verified = verify_suite(folder)
    evaluation = json.loads((folder / "evaluation.json").read_text())
    runs = json.loads((folder / "agent_runs.json").read_text())
    recalculated = []
    for pair in runs:
        row, _ = evaluate_run(folder / pair["path"], pair["case"])
        row["elapsed_s"] = pair["elapsed_s"]
        recalculated.append(row)
    assert recalculated == evaluation["rows"], "saved scores differ from recomputation"
    assert summarize(recalculated) == evaluation["summary"], "summary differs from raw scores"
    for path in (folder / "methods").glob("*.json"):
        row = json.loads(path.read_text())
        assert row["status"] == "completed", f"failed method attempt: {path.name}"
        graph = validation_input(row["case"]).graph
        for label in ("primary", "secondary"):
            scope = row.get(label)
            if not scope or scope["status"] != "completed":
                continue
            target = graph if label == "primary" else graph.subgraph(max(nx.connected_components(graph), key=len))
            for method in ("louvain", "leiden"):
                result = scope["methods"][method]
                parts = [set(p) for p in result["partition"]]
                assert validate_partition(target, parts) == result["disconnected_communities"]
                assert math.isclose(nx.community.modularity(target, parts), result["q"], abs_tol=1e-12)
                values = result["null_values"]
                assert len(values) == len(scope["null_hashes"]) == 99
                e = sum(q >= result["q"] for q in values)
                assert result["exceedances"] == e
                assert result["p_value"] == (1 + e) / 100
    return {**verified, "recomputed_scores": len(recalculated), "method_arithmetic": "verified"}


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1])), sort_keys=True))
