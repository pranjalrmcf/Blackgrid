"""Sprint 4 live pilot (protocols/sprint04_live_pilot.md, s4-v3): a real model on fresh synthetic cases.

Paid calls happen only through the existing durable workflow, with explicit `allow_paid` from the
CLI. Live runs are stored in the main runs/ store, so every existing spend cap keeps counting prior
spend. A pilot-level cap is enforced by lowering each run's per-investigation cap to what is left.
"""
from __future__ import annotations

import csv
import json
import random
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from blackgrid.agent.roles import PROMPT_VERSION, InvestigationInput
from blackgrid.evaluation.benchmark import dev_cases
from blackgrid.contracts import RunConfig, canonical_sha256
from blackgrid.agent.critic import CRITIC_VERSION
from blackgrid.evaluation.scoring import evaluate_run, expectation, failure_row, resolve, summarize, verify_artifacts
from blackgrid.workflow.runner import REPO_ROOT, capture_environment, run_investigation
from blackgrid.evaluation.sprint3 import append, save, sha
from blackgrid.evaluation.sprint4 import EVALUATOR_VERSION, RuleBaselineProvider, assess_claim_s4
from blackgrid.evaluation.validation import (CASE_IDS, S4_CASE_IDS, S4LIVE_CASE_IDS, S4V2_CASE_IDS, case_index,
                                  public_registry, validation_input, validation_spec)
from blackgrid.workflow.api import open_services

SUITE_VERSION = "s4-live-v1"
PROTOCOL = "protocols/sprint04_live_pilot.md"
MODEL = "deepseek/deepseek-v4-flash-0731"
ARMS = ("baseline", "tool_only", "validated")
LIVE_ARMS = ("tool_only", "validated")
MIN_REMAINING_USD = 0.03  # about two worst-case reservations (protocol §4)
STRENGTH = re.compile(r"\b(strong(ly)?|weak(ly)?|substantial(ly)?|pronounced|clear(ly)?|robust(ly)?|real|genuine)\b",
                      re.I)
CAUSAL = re.compile(r"\b(caus\w*|drives?|driven by|leads? to|because of|due to|results? in|influenc\w*)\b", re.I)
REGISTERED = re.compile(r"\bpre-?registered\b", re.I)
ISO = re.compile(r"\d{4}-\d{2}-\d{2}(T[\d:.]+Z?)?")
NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.]?\d)(%?)")


def _config(cid: str, arm: str, per_run_usd: float) -> RunConfig:
    case = validation_input(cid)
    data = {"dataset": {"dataset_id": "synthetic-validation", "path": "benchmarks/validation", "sha256": "0" * 64,
                        "source_url": "local-synthetic",
                        "citations": ["BLACKGRID independently generated synthetic validation instances"],
                        "rights_status": "accepted_local_noncommercial", "rights_decision": "D-051"},
            "condition": "tool_only" if arm == "tool_only" else "validated", "question": case.public.question,
            "experiment": validation_spec(cid).model_dump(mode="json")}
    if arm in LIVE_ARMS:
        data |= {"mode": "live", "paid_execution_authorized": True,
                 "llm": {"model": MODEL, "max_tokens_per_call": 16_000, "request_timeout_s": 240},
                 "budget": {"max_usd_per_investigation": round(per_run_usd, 6)}}
    return RunConfig.model_validate(data)


def pilot_spend(runs_dir: Path, run_ids: list[str]) -> float:
    """USD for the pilot's runs from durable operation rows (open reservations count in full)."""
    services = open_services(runs_dir)
    try:
        return sum(services.store.run_totals(rid)["usd"] for rid in run_ids)
    finally:
        services.close()


def claim_diagnostics(claim: dict, documents: dict) -> dict:
    """Descriptive checks for free prose, independent of critic.py (protocol §5.2)."""
    text = str(claim.get("text", ""))
    values = []
    for link in claim.get("evidence", []) if isinstance(claim.get("evidence"), list) else []:
        try:
            value = resolve(documents, link)
        except (KeyError, ValueError, IndexError, TypeError):
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(value)
    unbound = []
    for m in NUM.finditer(ISO.sub(" ", text)):
        token, percent = m.group(0).rstrip("%"), m.group(1) == "%"
        decimals = len(token.split(".")[1]) if "." in token else 0
        ok = any(abs(round(v * (100 if percent else 1), decimals) - float(token)) < 1e-9 for v in values)
        if not ok:
            unbound.append(m.group(0))
    return {"numbers_bound": not unbound, "unbound_numbers": unbound[:5],
            "strength_wording": bool(STRENGTH.search(text)), "causal_wording": bool(CAUSAL.search(text)),
            "preregistered_wording": bool(REGISTERED.search(text))}


def freeze(output: Path, cap_usd: float) -> dict:
    names = [PROTOCOL, "docs/sprint04_review_rubric.md", "pyproject.toml", "uv.lock"]
    names += [p.relative_to(REPO_ROOT).as_posix() for p in sorted((REPO_ROOT / "src/blackgrid").rglob("*.py"))]
    receipt = {"suite": SUITE_VERSION, "started_utc": datetime.now(UTC).isoformat(),
               "environment": capture_environment().model_dump(mode="json"),
               "source_hashes": {name: sha(REPO_ROOT / name) for name in names},
               "versions": {"evaluator": EVALUATOR_VERSION, "critic": CRITIC_VERSION, "prompt": PROMPT_VERSION,
                            "baseline": RuleBaselineProvider.model, "model": MODEL},
               "arms": list(ARMS), "case_ids": list(S4LIVE_CASE_IDS), "pilot_cap_usd": cap_usd,
               "authorization": "user: 'Run the live pilot with deepseek-v4-flash, max $0.50 total'",
               "accounting": "main runs/ store; store sprint label 'sprint2' retained (stricter, nothing reset); "
                             "attributed to the Sprint 4 live pilot",
               "specs": {cid: validation_spec(cid).model_dump(mode="json") for cid in S4LIVE_CASE_IDS}}
    save(output / "freeze.json", receipt)
    return receipt


def run_pilot(output: Path, *, cap_usd: float = 0.50, allow_paid: bool = False, runs_dir: Path | None = None,
              provider=None, case_ids: tuple[str, ...] = S4LIVE_CASE_IDS) -> Path:
    """Execute s4-v3 once. `provider` replaces the live provider in tests only (a fake paid provider)."""
    if not allow_paid:
        raise PermissionError("the live pilot makes paid calls; pass allow_paid=True (CLI: --allow-paid)")
    if not 0 < cap_usd <= 0.50:
        raise ValueError("pilot cap must be in (0, 0.50] USD as authorized")
    runs_dir = (runs_dir or REPO_ROOT / "runs").resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    receipt = freeze(output, cap_usd)
    attempts = output / "attempts.jsonl"
    pairs: list[dict] = []
    errors: list[dict] = []
    live_ids: list[str] = []
    status, stop_reason = "running", None

    def check_freeze() -> None:
        for name, expected in receipt["source_hashes"].items():
            if sha(REPO_ROOT / name) != expected:
                raise ValueError("frozen implementation changed: " + name)

    try:
        registry = public_registry(case_ids)
        hashes = [c["projection_sha256"] for c in registry["cases"]]
        seen = {c.record.projection_sha256 for c in dev_cases().values()}
        for earlier in (CASE_IDS, S4_CASE_IDS, S4V2_CASE_IDS):
            seen |= {c["projection_sha256"] for c in public_registry(earlier)["cases"]}
        overlap = sorted(set(hashes) & seen)
        save(output / "overlap_check.json", {"cases": len(hashes), "fresh": len(set(hashes)),
                                             "exact_overlaps": len(overlap)})
        if overlap or len(set(hashes)) != len(hashes):
            raise ValueError("overlap with earlier cases; no paid call was made")
        save(output / "registry.json", registry)
        for cid in case_ids:
            case = validation_input(cid)
            for arm in ARMS:
                check_freeze()
                label = f"s4live-{cid}-{arm}"
                remaining = cap_usd - pilot_spend(runs_dir, live_ids)
                if arm in LIVE_ARMS and (stop_reason or remaining < MIN_REMAINING_USD):
                    stop_reason = stop_reason or f"pilot budget remaining USD {remaining:.4f} < {MIN_REMAINING_USD}"
                    append(attempts, {"attempt": label, "state": "not_run_budget", "reason": stop_reason})
                    pairs.append({"case": cid, "arm": arm, "path": None, "not_run": stop_reason})
                    continue
                append(attempts, {"attempt": label, "state": "started", "remaining_usd": round(remaining, 6)})
                before = time.perf_counter()
                try:
                    inp = InvestigationInput(case_id=cid, question=case.public.question,
                                             request=case.public.request | {'summary_mode':'model'},
                                             graph=case.graph, record=case.record, spec=validation_spec(cid))
                    config = _config(cid, arm, min(cap_usd, remaining))
                    use = RuleBaselineProvider() if arm == "baseline" else provider
                    out = run_investigation(inp, config, use, runs_dir, cache_dir=None,
                                            input_ref={"kind": "validation", "case_id": cid}, run_prefix=label + "-",
                                            allow_paid=arm in LIVE_ARMS,
                                            reproduce="(paid; not rerun without new authorization)")
                    if arm in LIVE_ARMS:
                        live_ids.append(out.outcome.run_id)
                    item = {"case": cid, "arm": arm, "path": str(out.run_dir), "run_id": out.outcome.run_id,
                            "status": out.outcome.status, "reason": out.outcome.reason,
                            "elapsed_s": time.perf_counter() - before,
                            "config_sha256": canonical_sha256(config),
                            "usd": pilot_spend(runs_dir, [out.outcome.run_id]) if arm in LIVE_ARMS else 0.0}
                    pairs.append(item)
                    append(attempts, {"attempt": label, "state": "finished", **item})
                    print(f"{label}: {out.outcome.status} (USD {item['usd']:.4f}, pilot total "
                          f"{pilot_spend(runs_dir, live_ids):.4f})", flush=True)
                    if out.outcome.status == "paused":  # e.g. billing unknown: a person must reconcile
                        stop_reason = f"run {out.outcome.run_id} paused: {out.outcome.reason}"
                except Exception as exc:
                    error = {"attempt": label, "state": "failed", "error": type(exc).__name__ + ": " + str(exc)[:300]}
                    errors.append(error)
                    append(attempts, error)
                    print(f"{label}: failed ({type(exc).__name__})", flush=True)
        save(output / "agent_runs.json", pairs)
        save(output / "evaluator_private/expectations.json", [expectation(c, case_index(c)) for c in S4LIVE_CASE_IDS])
        rows, blind = [], []
        for pair in pairs:
            if not pair.get("path"):
                continue
            try:
                folder = Path(pair["path"])
                row, scored = evaluate_run(folder, pair["case"], index=case_index(pair["case"]), assess=assess_claim_s4)
                docs = verify_artifacts(folder)
                diags = [claim_diagnostics(item["claim"], docs) for item in scored]
                row |= {"condition": pair["arm"], "elapsed_s": pair["elapsed_s"],
                        "numbers_bound": sum(d["numbers_bound"] for d in diags),
                        "strength_wording": sum(d["strength_wording"] for d in diags),
                        "causal_wording": sum(d["causal_wording"] for d in diags),
                        "preregistered_wording": sum(d["preregistered_wording"] for d in diags)}
                rows.append(row)
                if pair["arm"] in LIVE_ARMS:
                    for item, diag in zip(scored, diags):
                        blind.append({"case": pair["case"], "arm": pair["arm"], "claim": item["claim"],
                                      "automated": item["assessment"], "diagnostics": diag,
                                      "cited_evidence": {link: resolve(docs, link)
                                                         for link in item["claim"].get("evidence", [])
                                                         if isinstance(link, str) and _resolvable(docs, link)}})
            except Exception as exc:
                error = {"attempt": pair.get("run_id"), "phase": "evaluation", "error": type(exc).__name__ + ": "
                         + str(exc)[:300]}
                errors.append(error)
                append(attempts, error)
        recorded = {(r["case"], r["condition"]) for r in rows}
        for pair in pairs:
            if (pair["case"], pair["arm"]) not in recorded:
                row = failure_row(pair["case"], pair["arm"], case_index(pair["case"]))
                if pair.get("not_run"):
                    row["status"] = "not_run_budget"
                rows.append(row)
        _export_blind(output, blind)
        summary = summarize(rows, ARMS, (("validated", "tool_only"), ("validated", "baseline")))
        for arm in ARMS:
            group = [r for r in rows if r["condition"] == arm]
            summary[arm] |= {"numbers_bound": sum(r.get("numbers_bound", 0) for r in group),
                             "strength_wording": sum(r.get("strength_wording", 0) for r in group),
                             "causal_wording": sum(r.get("causal_wording", 0) for r in group),
                             "preregistered_wording": sum(r.get("preregistered_wording", 0) for r in group),
                             "not_run_budget": sum(r["status"] == "not_run_budget" for r in group),
                             "wall_s": sum(r.get("elapsed_s", 0) or 0 for r in group)}
        save(output / "evaluation.json", {"version": EVALUATOR_VERSION, "rows": rows, "summary": summary,
                                           "errors": errors, "claim_review": "pending (blinded_claims.csv)"})
        status = "completed" if not errors and not stop_reason else "partial"
    except Exception as exc:
        errors.append({"phase": "suite", "error": type(exc).__name__ + ": " + str(exc)[:300]})
        append(attempts, {"state": "failed", **errors[-1]})
        status = "failed"
    except BaseException as exc:
        errors.append({"phase": "suite", "error": type(exc).__name__ + ": " + (str(exc)[:300] or "interrupted")})
        append(attempts, {"state": "interrupted", **errors[-1]})
        status = "interrupted"
        raise
    finally:
        total = pilot_spend(runs_dir, live_ids)
        save(output / "suite.json", {"suite": SUITE_VERSION, "status": status, "stop_reason": stop_reason,
                                     "finished_utc": datetime.now(UTC).isoformat(),
                                     "elapsed_s": time.perf_counter() - started, "live_runs": live_ids,
                                     "pilot_usd": total, "pilot_cap_usd": cap_usd, "errors": errors,
                                     "model": MODEL, "claim_review": "pending"})
    return output


def _resolvable(docs: dict, link: str) -> bool:
    try:
        resolve(docs, link)
        return True
    except (KeyError, ValueError, IndexError, TypeError):
        return False


def _export_blind(output: Path, blind: list[dict]) -> None:
    random.Random(7353).shuffle(blind)
    mapping = []
    with (output / "blinded_claims.csv").open("x", encoding="utf-8", newline="") as stream:
        fields = ["review_id", "claim", "cited_evidence", "reviewer", "support", "strength_wording",
                  "comparison_complete", "misleading", "confidence", "notes"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for i, item in enumerate(blind, 1):
            rid = f"live-{i:03}"
            writer.writerow({"review_id": rid, "claim": str(item["claim"].get("text", "")),
                             "cited_evidence": json.dumps(item["cited_evidence"], sort_keys=True)})
            mapping.append({"review_id": rid, **item})
    save(output / "evaluator_private/blind_mapping.json", mapping)


def export_summary(output: Path, destination: Path) -> Path:
    evaluation = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
    suite = json.loads((output / "suite.json").read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "summary.json"
    path.write_text(json.dumps({"suite": suite["suite"], "status": suite["status"], "stop_reason": suite["stop_reason"],
                                "model": suite["model"], "pilot_usd": suite["pilot_usd"],
                                "pilot_cap_usd": suite["pilot_cap_usd"], "elapsed_s": suite["elapsed_s"],
                                "errors": suite["errors"], "evaluator": evaluation["version"],
                                "summary": evaluation["summary"], "claim_review": "pending",
                                "freeze_sha256": sha(output / "freeze.json")}, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path
