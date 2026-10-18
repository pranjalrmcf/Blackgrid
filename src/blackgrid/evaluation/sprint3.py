"""One offline Sprint 3 workflow, with a freeze receipt and append-only attempts.

All local run details stay under runs/. Exported summaries contain synthetic aggregates
only. Paid providers and sealed-test loaders are deliberately absent from this workflow.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import random
import time
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx

from blackgrid.agent.roles import InvestigationInput, PROMPT_VERSION
from blackgrid.evaluation.benchmark import dev_cases
from blackgrid.contracts import EdgeStatus, RunConfig, canonical_sha256
from blackgrid.evaluation.scoring import EVALUATOR_VERSION, evaluate_run, expectation, failure_row, resolve, summarize, verify_artifacts
from blackgrid.analysis.methods import (ADAPTER_VERSION, MethodSpec, backend_versions, compare_scope,
                               comparison_verdict, variation_information)
from blackgrid.agent.providers import MockProvider
from blackgrid.workflow.runner import REPO_ROOT, capture_environment, run_investigation
from blackgrid.agent.tools import network_denied
from blackgrid.evaluation.validation import CASE_IDS, VALIDATION_VERSION, public_registry, validation_input, validation_spec

SUITE_VERSION = "s3-suite-v1.1"
TOTAL_TIMEOUT_S = 2700


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: neither reruns nor repairs silently rewrite scientific outputs.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def append(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"utc": datetime.now(UTC).isoformat(), **value}, sort_keys=True) + "\n")
        stream.flush()


def freeze(output: Path) -> dict:
    names = ["protocols/sprint03_evaluation.md", "pyproject.toml", "uv.lock"]
    names += [p.relative_to(REPO_ROOT).as_posix() for p in sorted((REPO_ROOT / "src/blackgrid").rglob("*.py"))]
    receipt = {"suite": SUITE_VERSION, "started_utc": datetime.now(UTC).isoformat(),
               "environment": capture_environment().model_dump(mode="json"),
               "hardware": {"machine": platform.machine(), "processor": platform.processor(),
                            "execution": "one trusted CPU task; cooperative timeouts; memory not OS-enforced"},
               "source_hashes": {name: sha(REPO_ROOT / name) for name in names},
               "versions": {"generator": VALIDATION_VERSION, "evaluator": EVALUATOR_VERSION,
                            "adapter": ADAPTER_VERSION, "prompt": PROMPT_VERSION, "model": MockProvider.model},
               "specs": {cid: validation_spec(cid).model_dump(mode="json") for cid in CASE_IDS},
               "method_spec": MethodSpec().model_dump(mode="json"), "total_timeout_s": TOTAL_TIMEOUT_S,
               "mode": "mock", "paid_cost_usd": 0, "sealed_tests": "not opened or generated"}
    try:
        receipt["backend_versions"] = backend_versions()
    except Exception as exc:
        receipt["backend_error"] = type(exc).__name__
    save(output / "freeze.json", receipt)
    return receipt


def check_freeze(receipt: dict) -> None:
    for name, expected in receipt["source_hashes"].items():
        if sha(REPO_ROOT / name) != expected:
            raise ValueError("frozen implementation changed: " + name)


def _config(case, condition: str) -> RunConfig:
    return RunConfig.model_validate({
        "dataset": {"dataset_id": "synthetic-validation", "path": "benchmarks/validation",
                    "sha256": "0" * 64, "source_url": "local-synthetic",
                    "citations": ["BLACKGRID independently generated synthetic validation instances"],
                    "rights_status": "accepted_local_noncommercial", "rights_decision": "D-051"},
        "condition": condition, "question": case.public.question,
        "experiment": validation_spec(case.public.case_id).model_dump(mode="json")})


def export_blind(output: Path, assessed: list[dict]) -> None:
    random.Random(7352).shuffle(assessed)
    mapping = []
    with (output / "blinded_claims.csv").open("x", encoding="utf-8", newline="") as stream:
        fields = ["review_id", "claim", "cited_evidence", "human_support", "human_reason"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for i, item in enumerate(assessed, 1):
            review_id = f"review-{i:03}"
            writer.writerow({"review_id": review_id, "claim": item["claim"]["text"],
                             "cited_evidence": json.dumps(item["cited_evidence"], sort_keys=True),
                             "human_support": "", "human_reason": ""})
            mapping.append({"review_id": review_id, **item})
    save(output / "evaluator_private/blind_mapping.json", mapping)


def run_suite(output: Path) -> Path:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    deadline = started + TOTAL_TIMEOUT_S
    receipt = freeze(output)  # before graph generation or validation outcomes
    attempts = output / "attempts.jsonl"
    pairs, method_rows, errors = [], [], []
    status = "running"

    def guard():
        if time.perf_counter() > deadline:
            raise TimeoutError("Sprint 3 total cooperative budget exhausted")
        check_freeze(receipt)

    try:
        with network_denied():
            registry = public_registry()
            hashes = [c["projection_sha256"] for c in registry["cases"]]
            development = {c.record.projection_sha256 for c in dev_cases().values()}
            if len(set(hashes)) != 24 or development.intersection(hashes):
                raise ValueError("duplicate validation graph or development overlap")
            save(output / "registry.json", registry)
            for cid in CASE_IDS:
                case = validation_input(cid)
                for condition in ("tool_only", "validated"):
                    guard()
                    label = f"{cid}-{condition}"
                    append(attempts, {"attempt": label, "state": "started", "phase": "agent"})
                    before = time.perf_counter()
                    try:
                        config = _config(case, condition)
                        inp = InvestigationInput(case_id=cid, question=case.public.question,
                                                 request=case.public.request, graph=case.graph, record=case.record,
                                                 spec=validation_spec(cid))
                        out = run_investigation(inp, config, MockProvider(), output / "investigations",
                                                cache_dir=None, input_ref={"kind": "validation", "case_id": cid},
                                                run_prefix=label + "-", reproduce=
                                                "uv run --frozen --extra methods blackgrid sprint3 --output NEW_DIRECTORY")
                        item = {"case": cid, "condition": condition,
                                "path": str(out.run_dir.relative_to(output)),
                                "elapsed_s": time.perf_counter() - before,
                                "config_sha256": canonical_sha256(config)}
                        pairs.append(item)
                        append(attempts, {"attempt": label, "state": "finished", **item,
                                          "status": out.outcome.status})
                        print(f"agent {label}: {out.outcome.status}", flush=True)
                    except Exception as exc:
                        error = {"attempt": label, "phase": "agent", "state": "failed",
                                 "error": type(exc).__name__ + ": " + str(exc)[:300]}
                        errors.append(error)
                        append(attempts, error)
                        print(f"agent {label}: failed ({type(exc).__name__})", flush=True)
            # No evaluator keys or family metadata have been written during investigations.
            save(output / "agent_runs.json", pairs)
            for cid in CASE_IDS[:18]:
                case = validation_input(cid)
                for master in MethodSpec().seeds:
                    guard()
                    label = f"{cid}-seed{master}"
                    append(attempts, {"attempt": label, "phase": "methods", "state": "started"})
                    before = time.perf_counter()
                    try:
                        primary = compare_scope(case.graph, master, "whole_graph", MethodSpec())
                        connected = nx.is_connected(case.graph)
                        secondary = None
                        if not connected and primary["status"] == "completed":
                            largest = case.graph.subgraph(max(nx.connected_components(case.graph), key=len)).copy()
                            secondary = compare_scope(largest, master, "largest_component", MethodSpec())
                        row = {"case": cid, "seed": master, "status": "completed",
                               "primary": primary, "secondary": secondary,
                               "verdicts": {method: comparison_verdict(primary, secondary, connected, method,
                                   case.record.edge_status_counts.get(EdgeStatus.UNKNOWN, 0))
                                   for method in ("louvain", "leiden")},
                               "elapsed_s": time.perf_counter() - before}
                        save(output / f"methods/{label}.json", row)
                        method_rows.append(row)
                        append(attempts, {"attempt": label, "phase": "methods", "state": "finished",
                                          "primary_status": primary["status"], "elapsed_s": row["elapsed_s"]})
                        print(f"methods {label}: {row['verdicts']}", flush=True)
                    except Exception as exc:
                        error = {"attempt": label, "phase": "methods", "state": "failed",
                                 "error": type(exc).__name__ + ": " + str(exc)[:300]}
                        errors.append(error)
                        save(output / f"methods/{label}.json", error)
                        append(attempts, error)
                        print(f"methods {label}: failed ({type(exc).__name__})", flush=True)
            guard()
            # Keys are available only to the trusted evaluator, after every investigation.
            save(output / "evaluator_private/expectations.json", [expectation(c) for c in CASE_IDS])
            rows, blind = [], []
            for pair in pairs:
                try:
                    folder = output / pair["path"]
                    row, claims = evaluate_run(folder, pair["case"])
                    row["elapsed_s"] = pair["elapsed_s"]
                    docs = verify_artifacts(folder)
                    for claim in claims:
                        blind.append({"case": pair["case"], "condition": pair["condition"], **claim,
                                      "cited_evidence": {link: resolve(docs, link)
                                                         for link in claim["claim"].get("evidence", [])}})
                    rows.append(row)
                except Exception as exc:
                    error = {"attempt": pair["path"], "phase": "evaluation", "state": "failed",
                             "error": type(exc).__name__ + ": " + str(exc)[:300]}
                    errors.append(error)
                    append(attempts, error)
            recorded = {(row["case"], row["condition"]) for row in rows}
            for cid in CASE_IDS:
                for condition in ("tool_only", "validated"):
                    if (cid, condition) not in recorded:
                        rows.append(failure_row(cid, condition))
            save(output / "evaluation.json", {"version": EVALUATOR_VERSION, "rows": rows,
                                               "summary": summarize(rows), "expected_case_conditions": 48,
                                               "evaluated_case_conditions": sum(not r.get("claim_counts_unknown", False)
                                                                                for r in rows), "errors": errors})
            export_blind(output, blind)
            save(output / "method_summary.json", method_summary(method_rows))
            status = "completed" if not errors and len(rows) == 48 and len(method_rows) == 54 else "partial"
    except Exception as exc:
        errors.append({"phase": "suite", "error": type(exc).__name__ + ": " + str(exc)[:300]})
        append(attempts, {"state": "failed", **errors[-1]})
        status = "failed"
    except BaseException as exc:  # KeyboardInterrupt/SystemExit: the process is ending, not running (R5)
        errors.append({"phase": "suite", "error": type(exc).__name__ + ": " + (str(exc)[:300] or "interrupted"),
                       "resumable": False, "note": "rerun the suite in a NEW output directory"})
        append(attempts, {"state": "interrupted", **errors[-1]})
        status = "interrupted"
        raise
    finally:
        # Root record preserves a failed attempt too; no result is silently replaced.
        save(output / "suite.json", {"suite": SUITE_VERSION, "status": status,
                                    "finished_utc": datetime.now(UTC).isoformat(),
                                    "elapsed_s": time.perf_counter() - started, "agent_runs": len(pairs),
                                    "method_runs": len(method_rows), "errors": errors,
                                    "llm_mode": "mock", "paid_cost_usd": 0, "human_review": "pending",
                                    "artifacts": {p.relative_to(output).as_posix(): sha(p) for p in output.rglob("*")
                                                  if p.is_file() and "investigations" not in p.relative_to(output).parts}})
    return output


def method_summary(rows: list[dict]) -> dict:
    output = {"expected_graph_seeds": 54, "finished_graph_seeds": len(rows), "methods": {}}
    for method in ("louvain", "leiden"):
        parts = [r["primary"]["methods"][method] for r in rows if r["primary"]["status"] == "completed"]
        stability = []
        for cid in CASE_IDS[:18]:
            group = [r for r in rows if r["case"] == cid and r["primary"]["status"] == "completed"]
            if len(group) == 3:
                found = [[set(p) for p in r["primary"]["methods"][method]["partition"]] for r in group]
                vis = [variation_information(found[i], found[j]) for i in range(3) for j in range(i + 1, 3)]
                qs = [r["primary"]["methods"][method]["q"] for r in group]
                stability.append({"case": cid, "mean_vi_nats": sum(vis) / 3, "q_range": max(qs) - min(qs),
                                  "verdicts": [r["verdicts"][method] for r in group]})
        output["methods"][method] = {"completed_primary": len(parts),
            "disconnected_observed_communities": sum(p["disconnected_communities"] for p in parts),
            "optimizer_elapsed_s": sum(p["optimizer_elapsed_s"] for p in parts),
            "verdict_counts": {v: sum(r["verdicts"][method] == v for r in rows)
                               for v in ("supported", "not_supported", "inconclusive", "abstain")},
            "stability": stability}
    output["paired_observed_q_leiden_minus_louvain"] = [
        {"case": r["case"], "seed": r["seed"],
         "delta": r["primary"]["methods"]["leiden"]["q"] - r["primary"]["methods"]["louvain"]["q"]}
        for r in rows if r["primary"]["status"] == "completed"]
    output["limitations"] = ["Exploratory optimization comparison, no scientific discovery ground truth.",
                              "Finite-swap null sampling is not proven mixed or exact.",
                              "Equal restarts are not equal compute; implementations differ.",
                              "Runtime is one machine, serial execution, no benchmark warmup.",
                              "No default switch or confirmatory multiple-method significance claim."]
    return output


def verify_suite(output: Path) -> dict:
    receipt = json.loads((output / "freeze.json").read_text(encoding="utf-8"))
    check_freeze(receipt)
    suite = json.loads((output / "suite.json").read_text(encoding="utf-8"))
    for name, expected in suite["artifacts"].items():
        path = (output / name).resolve()
        if not path.is_relative_to(output.resolve()) or sha(path) != expected:
            raise ValueError("suite artifact mismatch: " + name)
    for pair in json.loads((output / "agent_runs.json").read_text(encoding="utf-8")):
        evaluate_run(output / pair["path"], pair["case"])
    return {"status": suite["status"], "agent_runs": suite["agent_runs"], "method_runs": suite["method_runs"],
            "integrity": "verified"}
