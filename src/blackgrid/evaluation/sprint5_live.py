"""Small authorized structural pilot using the retained console/trial allowance."""
from __future__ import annotations

import json
import time
from pathlib import Path

from blackgrid.agent.roles import InvestigationInput
from blackgrid.contracts import EdgeRemovalSensitivity, ExperimentSpec, RunConfig
from blackgrid.agent.live_allowance import ensure_allowance, constrain, read_allowance, MODEL
from blackgrid.workflow.runner import REPO_ROOT, capture_environment, run_investigation, write_json
from blackgrid.evaluation.sprint5 import evaluation_input, score, source_hashes
from blackgrid.data.synthetic import erdos_renyi, planted_sbm
from blackgrid.workflow.api import open_services


def live_input(index: int, version: str = "s5-live-v1") -> InvestigationInput:
    if version not in ("s5-live-v1", "s5-live-v2") or index not in range(1, 3 if version == "s5-live-v2" else 5):
        raise ValueError("unknown pilot case")
    seed, cid = ((271001 + 100*(index-1), f"s5live2-{index:03}") if version == "s5-live-v2" else
                 (171001 + 100*(index-1), f"s5live-{index:03}"))
    sg, _ = erdos_renyi(cid, n=28, m=48, seed=seed) if index % 2 else planted_sbm(
        cid, blocks=3, block_size=10, p_in=.4, p_out=.025, seed=seed)
    question = "Which nodes have many contacts and high betweenness?" if index % 2 else "Which nodes connect different groups?"
    if index >= 3 or (version == "s5-live-v2" and index == 2):
        question += " Are the rankings stable under missing connections?"
    spec = ExperimentSpec(experiment_id=cid, graph_id=cid, status="exploratory",
        hypothesis="Describe network positions under fixed structural tools.", competing_explanations=("projection and missingness",),
        task="community_structure_vs_null", method="louvain", statistic="modularity", null_model="degree_preserving_double_edge_swap",
        null_replicates=99, seed=(281000 if version == "s5-live-v2" else 181000)+index,
        sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=.1, replicates=3))
    return InvestigationInput(cid, question, {"family": "auto", "method": "auto"}, sg.graph, sg.record, spec)


def run_pilot(output: Path, *, allow_paid: bool = False, provider=None) -> dict:
    if not allow_paid:
        raise PermissionError("live pilot needs --allow-paid")
    if output.exists() or not output.resolve().is_relative_to((REPO_ROOT / "runs").resolve()):
        raise ValueError("use a fresh output directory under runs/")
    output.mkdir(parents=True)
    runs = REPO_ROOT / "runs"
    allowance = ensure_allowance(runs)
    frozen = source_hashes(REPO_ROOT)
    write_json(output / "freeze.json", {"source_hashes": frozen, "protocol": "s5-live-v2", "model": MODEL,
        "environment": capture_environment().model_dump(mode="json"), "allowance": read_allowance(allowance, runs)})
    from blackgrid.evaluation.benchmark import dev_cases
    from blackgrid.evaluation.validation import CASE_IDS, S4_CASE_IDS, S4V2_CASE_IDS, S4LIVE_CASE_IDS, validation_input
    seen = {c.planner_view()[2].projection_sha256 for c in dev_cases().values()}
    seen |= {validation_input(cid).record.projection_sha256 for cid in CASE_IDS+S4_CASE_IDS+S4V2_CASE_IDS+S4LIVE_CASE_IDS}
    seen |= {evaluation_input(i).record.projection_sha256 for i in range(1, 17)}
    seen |= {live_input(i).record.projection_sha256 for i in range(1, 5)}
    inputs = [live_input(i, "s5-live-v2") for i in range(1, 3)]
    hashes = [inp.record.projection_sha256 for inp in inputs]
    overlap = len(set(hashes) & seen) + (len(hashes)-len(set(hashes)))
    write_json(output / "overlap_check.json", {"cases": 2, "overlaps": overlap})
    if overlap:
        raise ValueError("projection overlap: no paid dispatch")
    rows, stop, started = [], None, time.perf_counter()
    try:
        for index, inp in enumerate(inputs, 1):
            for arm in ("single", "adaptive"):
                row = {"case": inp.case_id, "arm": arm, "status": "started"}
                rows.append(row)
                write_json(output / "attempts.json", rows)
                if stop:
                    row.update(status="not_run", reason=stop)
                    continue
                if source_hashes(REPO_ROOT) != frozen:
                    raise ValueError("implementation changed during frozen pilot")
                raw = {"mode": "live", "paid_execution_authorized": True, "investigation_family": "auto", "planning_mode": arm,
                    "question": inp.question, "experiment": inp.spec.model_dump(mode="json"),
                    "dataset": {"dataset_id": "synthetic-s5-live", "path": "benchmarks/validation", "sha256": "0"*64,
                        "source_url": "local-synthetic", "citations": ["Independently generated BLACKGRID graphs"],
                        "rights_status": "accepted_local_noncommercial", "rights_decision": "independently generated"},
                    "llm": {"model": MODEL, "max_tokens_per_call": 16000, "reasoning_max_tokens": 12000, "request_timeout_s": 240}}
                inp.request["planning_mode"] = arm
                before = time.perf_counter()
                prefix = f"s5live2-{index:03}-{arm}-"
                try:
                    config = constrain(RunConfig.model_validate(raw), allowance, runs)
                    out = run_investigation(inp, config, provider, runs, cache_dir=None,
                        input_ref={"kind": "sprint5-live", "version": "s5-live-v2", "index": index}, run_prefix=prefix, allow_paid=True,
                        reproduce="Paid pilot; no automatic rerun. Replay the saved trace for free.")
                    row.update(score(out.run_dir, inp.graph, False), run_dir=out.run_dir.name,
                               elapsed_s=time.perf_counter()-before)
                    trace_path = out.run_dir / "llm_trace.jsonl"
                    trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines() if line] if trace_path.exists() else []
                    row["provider_reported_usd"] = sum(t["reported_usd"] for t in trace) if trace and all(t.get("reported_usd") is not None for t in trace) else None
                    row["truncated_calls"] = sum(t.get("finish_reason") == "length" for t in trace)
                    row["rejected_drafts"] = sum(not d.accepted for d in out.result.critic_decisions) if out.result else None
                    row["follow_up"] = out.result.follow_up if out.result else None
                    # Completeness requires the aggregate facts requested, not just any nonempty claim.
                    required_fields = ({"max_degree", "max_betweenness"} if index % 2 else {"communities", "max_cross_degree"})
                    if "stable" in inp.question:
                        required_fields.add("mean_top_jaccard")
                    cited_fields = {p.rsplit("/", 1)[-1] for c in out.result.reported_claims for p in c.get("evidence", [])} if out.result else set()
                    row["missing_facts"] = sorted(required_fields - cited_fields)
                    row["useful"] = row["useful"] and not row["missing_facts"]
                    if out.outcome.status in ("paused", "budget_exhausted"):
                        stop = f"{out.outcome.status}: {out.outcome.reason}"
                except Exception as exc:
                    row.update(status="failed", reason=f"{type(exc).__name__}: {str(exc)[:180]}")
                    stop = row["reason"]
                finally:
                    # Discover durable run IDs even if finalization raised; spending still counts globally.
                    services = open_services(runs)
                    try:
                        row["durable_run_ids"] = [r["run_id"] for r in services.store.runs() if r["run_id"].startswith(prefix)]
                    finally:
                        services.close()
                    write_json(output / "attempts.json", rows)
                print(f"{inp.case_id}/{arm}: {row['status']}; allowance used ${read_allowance(allowance, runs)['spent_usd']:.5f}", flush=True)
    finally:
        allowance_state = read_allowance(allowance, runs)
        summary = {"protocol": "s5-live-v2", "model": MODEL, "attempts": len(rows),
            "status": "completed" if len(rows)==4 and not stop else "partial", "stop_reason": stop,
            "elapsed_s": time.perf_counter()-started, "allowance": allowance_state, "arms": {}}
        summary["pilot_accounted_usd"] = sum(row.get("usd", 0) for row in rows)
        summary["provider_reported_usd"] = sum(row["provider_reported_usd"] for row in rows) if rows and all(row.get("provider_reported_usd") is not None for row in rows) else None
        for arm in ("single", "adaptive"):
            group = [r for r in rows if r["arm"] == arm]
            summary["arms"][arm] = {"attempts": len(group), "useful": sum(r.get("useful", False) for r in group),
                "claims": sum(r.get("claims", 0) for r in group), "unsupported": sum(r.get("unsupported", 0) for r in group),
                "calls": sum(r.get("calls", 0) for r in group), "tokens": sum(r.get("tokens", 0) for r in group),
                "accounted_usd": sum(r.get("usd", 0) for r in group)}
        write_json(output / "summary.json", summary)
    return summary
