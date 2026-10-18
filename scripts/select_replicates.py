"""Apply the exp-v1 §7 replicate-count rule using development cases only (runtime, never significance).

    uv run --frozen python scripts/select_replicates.py
"""

from __future__ import annotations

import json
import time

from blackgrid.evaluation.benchmark import dev_cases
from blackgrid.contracts import EdgeRemovalSensitivity, ExperimentSpec
from blackgrid.analysis.experiment import analyse

CANDIDATES = (99, 199, 499, 999)
BUDGET_S = 30.0


def main() -> None:
    cases = dev_cases()
    case = max(cases.values(), key=lambda c: c.record.unique_edges)
    timings = {}
    for replicates in CANDIDATES:
        spec = ExperimentSpec(
            experiment_id="replicate-timing", graph_id=case.public.case_id, status="exploratory", hypothesis="timing",
            competing_explanations=("n/a",), task="community_structure_vs_null", method="louvain",
            statistic="modularity", null_model="degree_preserving_double_edge_swap", null_replicates=replicates,
            seed=1, sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=0.1, replicates=20),
        )
        start = time.perf_counter()
        analyse(case.graph, spec, "whole_graph", start + 600)  # generous deadline: we are measuring
        timings[replicates] = round(time.perf_counter() - start, 3)
    chosen = max((r for r in CANDIDATES if 2 * timings[r] <= BUDGET_S), default=None)
    print(json.dumps({"case": case.public.case_id, "edges": case.record.unique_edges,
                      "single_analysis_seconds": timings, "doubled_budget_s": BUDGET_S, "chosen": chosen}, indent=2))


if __name__ == "__main__":
    main()
