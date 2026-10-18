"""Offline engineering evaluation; independent numerical and claim checks."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import networkx as nx

from blackgrid.agent.roles import InvestigationInput
from blackgrid.contracts import EdgeRemovalSensitivity, ExperimentSpec, RunConfig
from blackgrid.agent.providers import MockProvider
from blackgrid.workflow.runner import REPO_ROOT, capture_environment, run_investigation, write_json
from blackgrid.data.synthetic import erdos_renyi, planted_sbm


def source_hashes(root: Path) -> dict:
    files = [p for area in ("src", "tests", "protocols") for p in (root / area).rglob("*")
             if p.suffix in (".py", ".html", ".md")]
    files += [root / "pyproject.toml", root / "uv.lock"]
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


class RuleRouter(MockProvider):
    model = "rule-router-s5-v1"

    @staticmethod
    def _plan(payload):
        plan = MockProvider._plan(payload)
        if plan.get("decision") == "run" and not any(c["tool"] == "ranking_sensitivity" for c in plan["tool_calls"]):
            plan["tool_calls"].append({"tool": "ranking_sensitivity", "args": {}})
        return plan


def evaluation_input(index: int) -> InvestigationInput:
    graph_id, seed = f"s5-{index:03}", 91001 + 100 * (index - 1)
    generated, _ = (planted_sbm(graph_id, blocks=3, block_size=8, p_in=.5, p_out=.03, seed=seed)
                    if 9 <= index <= 12 else erdos_renyi(graph_id, n=32 if 5 <= index <= 8 else 24,
                                                       m=64 if 5 <= index <= 8 else 36, seed=seed))
    question = "Which nodes have many contacts and high betweenness?" if index % 2 else "Which nodes connect different groups?"
    if index % 3 == 0:
        question += " Are the rankings stable under missing connections?"
    if index > 12:
        question = "Who is influential?" if index % 2 else "Predict future interactions."
    spec = ExperimentSpec(experiment_id=graph_id, graph_id=graph_id, status="exploratory",
        hypothesis="Describe structural positions under the fixed tool contract.", competing_explanations=("graph construction",),
        task="community_structure_vs_null", method="louvain", statistic="modularity",
        null_model="degree_preserving_double_edge_swap", null_replicates=99, seed=101000+index,
        sensitivity=EdgeRemovalSensitivity(mechanism="uniform", removal_fraction=.1, replicates=3))
    return InvestigationInput(graph_id, question, {"family": "auto", "method": "auto"},
                              generated.graph, generated.record, spec)


def score(path: Path, graph: nx.Graph, refuse: bool) -> dict:
    """Independent saved-artifact scoring, no critic decisions or claim-builder imports."""
    manifest = json.loads((path / "manifest.json").read_text())
    errors = []
    for name, expected in manifest["artifacts"].items():
        if hashlib.sha256((path / name).read_bytes()).hexdigest() != expected:
            errors.append("hash:" + name)
    result = json.loads((path / "investigation.json").read_text())
    config = json.loads((path / "config.json").read_text())
    if refuse:
        if result["verdict"] != "rejected" or result["tool_calls"]:
            errors.append("unsupported task not refused before tools")
    for filename in ("node_centrality.json", "community_partition.json", "community_bridge.json"):
        if not (path / filename).exists():
            continue
        output = json.loads((path / filename).read_text())
        rows = output["rows"]
        if {r["node"] for r in rows} != {str(n) for n in graph} or len(rows) != len(graph):
            errors.append("node coverage:" + filename)
        if filename == "node_centrality.json":
            reference = nx.betweenness_centrality(graph, normalized=True)
            for row in rows:
                n = int(row["node"])
                if row["degree"] != graph.degree(n) or abs(row["betweenness"] - reference[n]) > 1e-9:
                    errors.append("centrality mismatch")
            if output["summary"]["max_degree"] != max(dict(graph.degree()).values(), default=0) or abs(
                    output["summary"]["max_betweenness"] - max(reference.values(), default=0)) > 1e-9:
                errors.append("centrality summary mismatch")
        if filename == "community_bridge.json":
            membership = {r["node"]: r["community"] for r in json.loads((path / "community_partition.json").read_text())["rows"]}
            for row in rows:
                n = int(row["node"])
                cross = sum(membership[str(n)] != membership[str(v)] for v in graph[n])
                if row["cross_degree"] != cross or abs(row["cross_fraction"] - (cross/graph.degree(n) if graph.degree(n) else 0)) > 1e-9:
                    errors.append("bridge mismatch")
    vocabulary = {
        "node_centrality.json#/summary/max_degree": "The maximum observed degree is",
        "node_centrality.json#/summary/max_betweenness": "The maximum normalized betweenness estimate is",
        "community_partition.json#/summary/communities": "The descriptive partition contains this many communities:",
        "community_bridge.json#/summary/max_cross_degree": "The maximum cross-community degree is",
        "ranking_sensitivity.json#/summary/mean_top_jaccard": "Mean tie-inclusive top-set Jaccard under assumed uniform edge removal is",
    }
    unsupported = 0
    for claim in result["reported_claims"]:
        links = claim.get("evidence", [])
        if len(links) != 1 or links[0] not in vocabulary:
            unsupported += 1; continue
        name, pointer = links[0].split("#")
        value = json.loads((path / name).read_text())
        for key in pointer.strip("/").split("/"):
            value = value[key]
        if claim["text"] != f"{vocabulary[links[0]]} {value}." or claim["evidence_level"] != "descriptive":
            unsupported += 1
    sensitivity = path / "ranking_sensitivity.json"
    if sensitivity.exists():
        summary = json.loads(sensitivity.read_text())["summary"]
        if summary["replicates"] != 3 or summary["removed_pair_status"] != "unknown" or not 0 <= summary["mean_top_jaccard"] <= 1:
            errors.append("sensitivity contract")
    tools = [c["tool"] for c in result["tool_calls"]]
    if not refuse:
        required = {"node_centrality"} if "contacts" in config["question"] else {"community_partition", "community_bridge"}
        if "stable" in config["question"]:
            required.add("ranking_sensitivity")
        if not required.issubset(tools):
            errors.append("required question evidence missing")
    if any(t in tools for t in ("community_test", "edge_removal_sensitivity")):
        errors.append("unrelated community-null calculation")
    if not refuse and not result["reported_claims"]:
        errors.append("no useful facts")
    cost = result["cost"]
    return {"status": result["status"], "useful": result["status"] == "completed" and not errors and not unsupported,
            "errors": errors, "unsupported": unsupported, "claims": len(result["reported_claims"]),
            "calls": cost["llm_calls"], "tokens": cost["input_tokens"] + cost["output_tokens"],
            "usd": cost["actual_usd"], "tools": tools}


def run_suite(output: Path) -> dict:
    from blackgrid.evaluation.benchmark import dev_cases
    from blackgrid.evaluation.validation import CASE_IDS, S4_CASE_IDS, S4V2_CASE_IDS, S4LIVE_CASE_IDS, validation_input
    if output.exists() or not output.resolve().is_relative_to((REPO_ROOT / "runs").resolve()):
        raise ValueError("use a fresh output directory under runs/")
    output.mkdir(parents=True)
    frozen = source_hashes(REPO_ROOT)
    write_json(output / "freeze.json", {"source_hashes": frozen, "environment": capture_environment().model_dump(mode="json"),
                                        "protocol": "s5-v1", "reviewer_basis": "independent numerical checks and fixed claim vocabulary"})
    old = {c.planner_view()[2].projection_sha256 for c in dev_cases().values()}
    old |= {validation_input(cid).record.projection_sha256 for cid in CASE_IDS + S4_CASE_IDS + S4V2_CASE_IDS + S4LIVE_CASE_IDS}
    rows, started, status, failure = [], time.perf_counter(), "running", None
    try:
        for i in range(1, 17):
            inp = evaluation_input(i)
            if inp.record.projection_sha256 in old:
                raise ValueError("projection overlap with prior or current cases")
            old.add(inp.record.projection_sha256)
            for arm in ("baseline", "single", "adaptive"):
                if time.perf_counter() - started > 600:
                    raise TimeoutError("suite cooperative 600-second budget exhausted")
                attempt = {"case": inp.case_id, "arm": arm, "status": "attempted"}
                rows.append(attempt)
                write_json(output / "attempts.json", rows)
                inp.request["planning_mode"] = "adaptive" if arm == "adaptive" else "single"
                config = RunConfig.model_validate({"dataset": {"dataset_id": "synthetic-s5", "path": "benchmarks/dev",
                    "sha256": "0"*64, "source_url": "local-synthetic", "citations": ["Independent BLACKGRID synthetic graphs"],
                    "rights_status": "accepted_local_noncommercial", "rights_decision": "independently generated"},
                    "question": inp.question, "investigation_family": "auto", "planning_mode": inp.request["planning_mode"],
                    "experiment": inp.spec.model_dump(mode="json")})
                result = run_investigation(inp, config, RuleRouter() if arm == "baseline" else MockProvider(), output,
                    cache_dir=None, input_ref={"kind": "sprint5", "index": i}, run_prefix=inp.case_id + "-" + arm + "-",
                    reproduce="python -m blackgrid sprint5 --output runs/NEW_NAME")
                attempt.update(score(result.run_dir, inp.graph, i > 12), run_dir=result.run_dir.name)
                write_json(output / "attempts.json", rows)
        if source_hashes(REPO_ROOT) != frozen:
            raise ValueError("source changed during evaluation")
        status = "completed"
    except BaseException as exc:
        status = "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed"
        failure = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        summary = {"protocol": "s5-v1", "status": status, "failure": failure, "elapsed_s": time.perf_counter()-started,
                   "attempts": len(rows), "mode": "scripted_offline", "real_llm_efficacy": "not_tested", "arms": {}}
        for arm in ("baseline", "single", "adaptive"):
            rr = [r for r in rows if r["arm"] == arm]
            summary["arms"][arm] = {"attempts": len(rr), "useful": sum(r.get("useful", False) for r in rr),
                "errors": sum(len(r.get("errors", [])) for r in rr), "unsupported": sum(r.get("unsupported", 0) for r in rr),
                "claims": sum(r.get("claims", 0) for r in rr), "calls": sum(r.get("calls", 0) for r in rr),
                "tool_calls": sum(len(r.get("tools", [])) for r in rr), "tokens": sum(r.get("tokens", 0) for r in rr),
                "usd": sum(r.get("usd", 0) for r in rr)}
        write_json(output / "summary.json", summary)
    return summary
