"""Evaluator-side development check: run the frozen exp-v1 procedure on every dev case and
compare its verdict and flags with the answer key. Reads answer keys, so it is an evaluator
tool; its output must never be fed to a planner or critic.

    uv run --frozen python scripts/dev_check.py [OUT_JSON]

Dev results are engineering checks, not efficacy evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from blackgrid.evaluation.benchmark import TaskType, dev_cases
from blackgrid.contracts import EdgeRemovalSensitivity, ExperimentSpec, canonical_sha256
from blackgrid.analysis.experiment import run_community_test

REPLICATES = 499  # exp-v1 §7 (decision log)


def main() -> None:
    rows = []
    for cid, case in dev_cases().items():
        spec = ExperimentSpec(
            experiment_id=f"devcheck-{cid}", graph_id=cid, status="exploratory",
            hypothesis="Best Louvain modularity exceeds degree-preserving randomizations.",
            competing_explanations=("degree heterogeneity", "disconnection", "sparsity"),
            task="community_structure_vs_null", method="louvain", statistic="modularity",
            null_model="degree_preserving_double_edge_swap", null_replicates=REPLICATES, seed=int(cid[-3:]),
            sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=0.1, replicates=20),
        )
        report = run_community_test(case.graph, spec, spec_sha256=canonical_sha256(spec))
        p, s = report.primary, report.secondary
        # Refusal tasks are decided before any experiment (Days 7-9); the experiment verdict is not their answer.
        scored = case.public.task_type is not TaskType.REFUSE_INVALID
        rows.append({
            "case": cid,
            "task": case.public.task_type.value,
            "verdict": report.verdict,
            "acceptable": list(case.key.acceptable_verdicts),
            "verdict_ok": (report.verdict in case.key.acceptable_verdicts) if scored else None,
            "required_flags": list(case.key.required_flags),
            "flags": list(report.flags),
            "Q_obs": p.result.observed_statistic,
            "null_mean": p.result.null.mean if p.result.null else None,
            "delta_q": p.delta_q,
            "z": p.z,
            "p": p.result.p_value,
            "lcc_p": s.result.p_value if s else None,
            "lcc_suitable": s.suitable if s else None,
            "abstain_reasons": list(p.unsuitable_reasons),
            "seconds": report.elapsed_s,
        })
    out = json.dumps(rows, indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)
        Path(sys.argv[1]).write_bytes(out.encode("utf-8"))
    for r in rows:
        fmt = lambda v: "-" if v is None else f"{v:.3f}"
        print(f"{r['case']}  {r['task'][:28]:28}  verdict={r['verdict']:13} ok={str(r['verdict_ok']):5} "
              f"Q={fmt(r['Q_obs'])} null={fmt(r['null_mean'])} dQ={fmt(r['delta_q'])} z={fmt(r['z'])} "
              f"p={fmt(r['p'])} lcc_p={fmt(r['lcc_p'])} flags={r['flags']} need={r['required_flags']} "
              f"t={r['seconds']:.1f}s")


if __name__ == "__main__":
    main()
