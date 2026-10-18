"""Mock-mode pilot: tool_only vs validated on the 8 development cases (Sprint 1 Day 11).

The evaluator below is the only code that reads answer keys, and it runs after both conditions
finish. Its support rubric (`eval-v1`) is versioned and partly overlaps the critic's rules (numbers,
causal language), which is a stated limitation: overlap inflates the critic's apparent benefit.
Mock outputs validate the plumbing only; they say nothing about a real model's behaviour.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from blackgrid.agent import InvestigationInput, flatten
from blackgrid.benchmark import BENCHMARK_VERSION, DevCase, TaskType, dev_cases
from blackgrid.contracts import EdgeRemovalSensitivity, ExperimentSpec, RunConfig
from blackgrid.critic import CAUSAL, STRUCTURE, unsupported_numbers
from blackgrid.providers import MockProvider
from blackgrid.runner import RunOutput, run_investigation, write_json

EVAL_VERSION = "eval-v1"
CONDITIONS = ("tool_only", "validated")
DEV_REPLICATES = 499


def dev_spec(case: DevCase) -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id=f"pilot-{case.public.case_id}", graph_id=case.public.case_id, status="exploratory",
        hypothesis="Best Louvain modularity exceeds degree-preserving randomizations.",
        competing_explanations=("degree heterogeneity", "disconnection", "sparsity"),
        task="community_structure_vs_null", method="louvain", statistic="modularity",
        null_model="degree_preserving_double_edge_swap", null_replicates=DEV_REPLICATES,
        seed=int(case.public.case_id[-3:]),
        sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=0.1, replicates=20))


def score_claim(claim: dict, evidence: dict, case: DevCase) -> tuple[bool, str]:
    """eval-v1: is this reported claim supported? Uses the answer key (evaluator-only)."""
    text = str(claim.get("text", ""))
    links = [p for p in claim.get("evidence", []) if isinstance(p, str)]
    if not links or any(p not in evidence for p in links):
        return False, "missing or unresolvable evidence"
    if unsupported_numbers(text, [evidence[p] for p in links]):
        return False, "number not in cited evidence"
    if CAUSAL.search(text) or claim.get("evidence_level") in ("identified_causal", "simulated_intervention"):
        return False, "causal claim without identification"
    if STRUCTURE.search(text) and "supported" not in case.key.acceptable_verdicts:
        return False, "asserts community structure where the key says none is detectable"
    if re.search(r"\bexceed\w*\b", text, re.I) and not re.search(r"\bnot\b", text, re.I):
        q = evidence.get("experiment_report.json#/primary/result/observed_statistic")
        mean = evidence.get("experiment_report.json#/primary/result/null/mean")
        if not (isinstance(q, float) and isinstance(mean, float) and q > mean):
            return False, "comparison contradicts the recorded values"
    return True, "supported"


def evaluate(case: DevCase, out: RunOutput) -> dict:
    result = out.result
    outputs = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in out.run_dir.glob("*.json")}
    evidence = flatten(outputs)
    claims = [c for c in result.reported_claims if isinstance(c, dict)]
    scored = [score_claim(c, evidence, case) for c in claims]
    refusal = case.public.task_type is TaskType.REFUSE_INVALID
    verdict_ok = result.verdict in case.key.acceptable_verdicts
    flags_ok = set(case.key.required_flags) <= set(result.flags)
    return {
        "case": case.public.case_id, "task": case.public.task_type.value, "condition": result.condition,
        "status": result.status.value, "verdict": result.verdict, "acceptable": list(case.key.acceptable_verdicts),
        "verdict_ok": verdict_ok, "required_flags": list(case.key.required_flags), "flags": list(result.flags),
        "flags_ok": flags_ok, "useful": verdict_ok and flags_ok, "refusal_task": refusal,
        "schema_ok": all(c.ok for c in result.llm_calls) and bool(result.llm_calls),
        "workflow_complete": result.status.value in ("completed", "abstained"),
        "claims": len(claims), "unsupported_claims": sum(not ok for ok, _ in scored),
        "unsupported_reasons": [why for ok, why in scored if not ok],
        "critic_rejections": sum(not d.accepted for d in result.critic_decisions), "revisions": result.revisions,
        "llm_calls": result.cost.llm_calls, "tokens": result.cost.input_tokens + result.cost.output_tokens,
        "usd": result.cost.actual_usd, "run_dir": out.run_dir.name,
    }


def summarise(rows: list[dict]) -> dict:
    table = {}
    for condition in CONDITIONS:
        r = [x for x in rows if x["condition"] == condition]
        claims = sum(x["claims"] for x in r)
        unsupported = sum(x["unsupported_claims"] for x in r)
        table[condition] = {
            "cases": len(r),
            "useful_coverage": f"{sum(x['useful'] for x in r)}/{len(r)}",
            "verdict_ok": f"{sum(x['verdict_ok'] for x in r)}/{len(r)}",
            "required_flags_present": f"{sum(x['flags_ok'] for x in r)}/{len(r)}",
            "unsupported_claim_rate": f"{unsupported}/{claims}" + (f" = {unsupported / claims:.2f}" if claims else ""),
            "abstained": sum(x["status"] == "abstained" for x in r),
            "failed": sum(x["status"] == "failed" for x in r),
            "schema_ok": f"{sum(x['schema_ok'] for x in r)}/{len(r)}",
            "llm_calls": sum(x["llm_calls"] for x in r), "tokens": sum(x["tokens"] for x in r),
            "usd": sum(x["usd"] for x in r),
        }
    return table


def run_pilot(runs_dir: Path, cache_dir: Path | None) -> Path:
    started = datetime.now(UTC)
    pilot_dir = runs_dir / f"pilot-{started:%Y%m%dT%H%M%SZ}"
    pilot_dir.mkdir(parents=True)
    rows = []
    for case in dev_cases().values():
        public, graph, record = case.planner_view()  # the investigation never sees case.key or case.truth
        for condition in CONDITIONS:
            config = RunConfig.model_validate({
                "dataset": {"dataset_id": "synthetic-dev", "path": "benchmarks/dev", "sha256": "0" * 64,
                            "source_url": "local-synthetic", "citations": ["BLACKGRID synthetic dev set"],
                            "rights_status": "accepted_local_noncommercial", "rights_decision": "D-019"},
                "condition": condition, "question": public.question})
            inp = InvestigationInput(case_id=public.case_id, question=public.question, request=public.request,
                                     graph=graph, record=record, spec=dev_spec(case))
            out = run_investigation(inp, config, MockProvider(), pilot_dir, cache_dir=cache_dir,
                                    run_prefix=f"{public.case_id}-{condition}-")
            rows.append(evaluate(case, out))  # evaluator step: reads the key only after the run
            print(f"  {public.case_id} {condition:9} -> {rows[-1]['verdict']:13} useful={rows[-1]['useful']}")
    summary = summarise(rows)
    write_json(pilot_dir / "pilot.json", {
        "benchmark": BENCHMARK_VERSION, "evaluator": EVAL_VERSION, "mode": "mock", "created_utc": started.isoformat(),
        "label": "Mock pilot: validates plumbing and the critic's catch rate on scripted mistakes only; "
                 "not evidence about real-model efficacy.",
        "summary": summary, "rows": rows})
    lines = ["# BLACKGRID mock pilot", "",
             "Mock mode: scripted naive planner/analyst. This validates plumbing only; it is **not** evidence that "
             "the critic improves a real model.", "",
             "| metric | " + " | ".join(CONDITIONS) + " |", "|---|" + "---|" * len(CONDITIONS)]
    for metric in summary[CONDITIONS[0]]:
        lines.append(f"| {metric} | " + " | ".join(str(summary[c][metric]) for c in CONDITIONS) + " |")
    lines += ["", "| case | condition | verdict | ok | flags ok | claims | unsupported |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['case']} | {r['condition']} | {r['verdict']} | {r['verdict_ok']} | {r['flags_ok']} | "
              f"{r['claims']} | {r['unsupported_claims']} |" for r in rows]
    (pilot_dir / "pilot.md").write_bytes("\n".join(lines).encode("utf-8"))
    from blackgrid.ui import write_pilot_page

    write_pilot_page(pilot_dir)
    return pilot_dir
