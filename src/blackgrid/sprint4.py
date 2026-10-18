"""Sprint 4 fresh offline evaluation (protocols/sprint04_evaluation.md, s4-v1).

Three matched arms per fresh case: a deterministic rule baseline, the scripted tool-only mock and
the validated mock with critic-v3. Scored by `s4-eval-v1`, which does not import critic.py or
pilot.py. Everything is offline; no paid provider is constructed here.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from blackgrid.agent import PROMPT_VERSION, InvestigationInput
from blackgrid.benchmark import dev_cases
from blackgrid.contracts import RunConfig, canonical_sha256
from blackgrid.critic import CRITIC_VERSION
from blackgrid.evaluation import (
    EVALUATOR_VERSION as S3_EVALUATOR_VERSION,
    NUMBER,
    PREFIX,
    assess_claim,
    evaluate_run,
    expectation,
    failure_row,
    numerical_verdict,
    summarize,
)
from blackgrid.providers import MockProvider, _ev, _request
from blackgrid.runner import REPO_ROOT, capture_environment, run_investigation
from blackgrid.sprint3 import append, save, sha
from blackgrid.tools import network_denied
from blackgrid.validation import (CASE_IDS, S4_CASE_IDS, S4LIVE_CASE_IDS, S4V2_CASE_IDS, case_index,
                                  public_registry, validation_input, validation_spec)

# Each protocol version has its own fresh case IDs; an inspected case set is never reused as unseen evidence.
PROTOCOLS = {"s4-v1": ("s4-suite-v1", "protocols/sprint04_evaluation.md", S4_CASE_IDS),
             "s4-v2": ("s4-suite-v2", "protocols/sprint04_evaluation_v2.md", S4V2_CASE_IDS)}
EVALUATOR_VERSION = "s4-eval-v1"
TOTAL_TIMEOUT_S = 3600
ARMS = ("baseline", "tool_only", "validated")
ALPHA = 0.05


# --- Arm 1: deterministic rule baseline (no model of any kind) ------------------------------------------


class RuleBaselineProvider(MockProvider):
    """Fixed rules in the provider slot: refuse what the allowlist forbids, otherwise template two claims."""

    name = "rule-baseline"
    model = "rule-baseline-v1"

    @staticmethod
    def _plan(payload: dict) -> dict:
        request = _request(payload)
        if str(request.get("method", "auto")) not in ("auto", "louvain") or request.get("claim_type") == "causal":
            return {"decision": "refuse", "tool_calls": [], "reason": "Request is outside the allowlisted protocol."}
        return {"decision": "run", "reason": "Fixed protocol: profile, null test, sensitivity.",
                "tool_calls": [{"tool": "profile_graph", "args": {}},
                               {"tool": "community_test", "args": {"method": "louvain"}},
                               {"tool": "edge_removal_sensitivity", "args": {}}]}

    @staticmethod
    def _analyse(payload: dict, revise: bool) -> dict:
        q, mean, p = (_ev(payload, f"primary/result/{f}") for f in ("observed_statistic", "null/mean", "p_value"))
        verdict = _ev(payload, "verdict")
        if not all(isinstance(v, (int, float)) for v in (q, mean, p)):
            return {"verdict": verdict if isinstance(verdict, str) else "abstain",
                    "flags": list(payload.get("flags", [])), "claims": []}
        return {"verdict": verdict, "flags": list(payload.get("flags", [])), "claims": [
            {"text": f"Modularity Q = {q:.3f} versus a degree-preserving null mean of {mean:.3f} (p = {p:.3f}).",
             "evidence_level": "descriptive",
             "evidence": [PREFIX + "observed_statistic", PREFIX + "null/mean", PREFIX + "p_value"]},
            {"text": f"The saved decision-rule verdict is '{verdict}' for this graph only.",
             "evidence_level": "descriptive", "evidence": ["experiment_report.json#/verdict"]}]}


# --- s4-eval-v1 claim rubric (independent of critic.py) -------------------------------------------------


def assess_claim_s4(claim: dict, documents: dict, *, preregistered_ok: bool = False) -> tuple[str, str]:
    """Protocol §3. Only the 'preregistered' verdict form differs between primary and sensitivity scoring."""
    text = str(claim.get("text", ""))
    links = claim.get("evidence", []) if isinstance(claim.get("evidence"), list) else []
    if re.fullmatch(r"Under the preregistered rule the verdict is '([^']+)' for this graph only\.", text):
        if not preregistered_ok:
            return "unsupported", "'preregistered' is not established by the cited field (D-058)"
        return assess_claim(claim, documents)
    match = re.fullmatch(r"The saved decision-rule verdict is '([^']+)' for this graph only\.", text)
    if match and claim.get("evidence_level") == "descriptive":
        try:
            cited = documents["experiment_report.json"]["verdict"] if "experiment_report.json#/verdict" in links \
                else None
            expected = numerical_verdict(documents["experiment_report.json"])
        except (KeyError, ValueError, TypeError):
            return "unsupported", "unresolvable evidence"
        ok = cited == match[1] == expected
        return ("supported", "verdict recomputed from saved evidence") if ok else ("unsupported", "verdict mismatch")
    match = re.fullmatch(rf"Observed modularity exceeds the null mean of ({NUMBER}) \(p = ({NUMBER})\)\.", text)
    if match:
        needed = [PREFIX + f for f in ("observed_statistic", "null/mean", "p_value")]
        if not all(link in links for link in needed):
            return "unsupported", "comparison does not cite observed Q, null mean and p"
        verdict, reason = assess_claim(claim, documents)
        p = documents["experiment_report.json"]["primary"]["result"].get("p_value")
        if verdict == "supported" and not (isinstance(p, (int, float)) and p <= ALPHA):
            return "unsupported", "literal comparison with p > 0.05 reads as a significant difference"
        return verdict, reason
    return assess_claim(claim, documents)  # numeric summary, strength, causal, unknown -> s3 rules


# --- the suite --------------------------------------------------------------------------------------------


def _config(cid: str, arm: str) -> RunConfig:
    case = validation_input(cid)
    return RunConfig.model_validate({
        "dataset": {"dataset_id": "synthetic-validation", "path": "benchmarks/validation", "sha256": "0" * 64,
                    "source_url": "local-synthetic",
                    "citations": ["BLACKGRID independently generated synthetic validation instances"],
                    "rights_status": "accepted_local_noncommercial", "rights_decision": "D-051"},
        "condition": "tool_only" if arm == "tool_only" else "validated", "question": case.public.question,
        "experiment": validation_spec(cid).model_dump(mode="json")})


def freeze(output: Path, protocol: str = "s4-v2") -> dict:
    suite, protocol_file, case_ids = PROTOCOLS[protocol]
    names = [protocol_file, "docs/sprint04_review_rubric.md", "pyproject.toml", "uv.lock"]
    names += [p.relative_to(REPO_ROOT).as_posix() for p in sorted((REPO_ROOT / "src/blackgrid").rglob("*.py"))]
    receipt = {"suite": suite, "protocol": protocol, "started_utc": datetime.now(UTC).isoformat(),
               "environment": capture_environment().model_dump(mode="json"),
               "hardware": {"machine": platform.machine(), "processor": platform.processor(),
                            "execution": "one trusted CPU task; cooperative timeouts; memory not OS-enforced"},
               "source_hashes": {name: sha(REPO_ROOT / name) for name in names},
               "versions": {"evaluator": EVALUATOR_VERSION, "s3_evaluator_reused": S3_EVALUATOR_VERSION,
                            "critic": CRITIC_VERSION, "prompt": PROMPT_VERSION, "mock": MockProvider.model,
                            "baseline": RuleBaselineProvider.model},
               "arms": list(ARMS), "case_ids": list(case_ids),
               "specs": {cid: validation_spec(cid).model_dump(mode="json") for cid in case_ids},
               "total_timeout_s": TOTAL_TIMEOUT_S, "mode": "mock", "paid_cost_usd": 0,
               "reviewer_basis": "review-rubric-v1 applied by Codex_AI; human gate waived by the user (D-059)",
               "sealed_tests": "not opened or generated"}
    save(output / "freeze.json", receipt)
    return receipt


def _check_freeze(receipt: dict) -> None:
    for name, expected in receipt["source_hashes"].items():
        if sha(REPO_ROOT / name) != expected:
            raise ValueError("frozen implementation changed: " + name)


def _score(output: Path, pairs: list[dict], errors: list[dict], attempts: Path, preregistered_ok: bool,
           case_ids: tuple[str, ...]) -> list[dict]:
    rows = []
    assess = partial(assess_claim_s4, preregistered_ok=preregistered_ok)
    for pair in pairs:
        try:
            row, _ = evaluate_run(output / pair["path"], pair["case"], index=case_index(pair["case"]), assess=assess)
            rows.append(row | {"condition": pair["arm"], "elapsed_s": pair["elapsed_s"]})
        except Exception as exc:
            if preregistered_ok:
                continue  # the primary pass already recorded this failure
            error = {"attempt": pair["path"], "phase": "evaluation", "state": "failed",
                     "error": type(exc).__name__ + ": " + str(exc)[:300]}
            errors.append(error)
            append(attempts, error)
    recorded = {(r["case"], r["condition"]) for r in rows}
    for cid in case_ids:
        for arm in ARMS:
            if (cid, arm) not in recorded:
                rows.append(failure_row(cid, arm, case_index(cid)))
    return rows


def run_suite(output: Path, protocol: str = "s4-v2") -> Path:
    suite_version, _, case_ids = PROTOCOLS[protocol]
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)  # a fresh directory; nothing is overwritten
    started = time.perf_counter()
    deadline = started + TOTAL_TIMEOUT_S
    receipt = freeze(output, protocol)  # before any graph of this protocol is generated
    attempts = output / "attempts.jsonl"
    pairs: list[dict] = []
    errors: list[dict] = []
    status = "running"

    def guard() -> None:
        if time.perf_counter() > deadline:
            raise TimeoutError("Sprint 4 total cooperative budget exhausted")
        _check_freeze(receipt)

    try:
        with network_denied():
            registry = public_registry(case_ids)
            hashes = [c["projection_sha256"] for c in registry["cases"]]
            seen = {c.record.projection_sha256 for c in dev_cases().values()}
            for earlier in (CASE_IDS, S4_CASE_IDS, S4V2_CASE_IDS, S4LIVE_CASE_IDS):  # other registered sets
                if earlier != case_ids:
                    seen |= {c["projection_sha256"] for c in public_registry(earlier)["cases"]}
            overlap = sorted(set(hashes) & seen)
            save(output / "overlap_check.json", {"fresh": len(set(hashes)), "cases": len(hashes),
                                                 "compared_against": "8 dev + all other validation case sets",
                                                 "exact_overlaps": len(overlap)})
            if len(set(hashes)) != len(case_ids) or overlap:
                raise ValueError("duplicate graph or overlap with development/earlier validation cases")
            save(output / "registry.json", registry)
            for cid in case_ids:
                case = validation_input(cid)
                for arm in ARMS:
                    guard()
                    label = f"{cid}-{arm}"
                    append(attempts, {"attempt": label, "state": "started"})
                    before = time.perf_counter()
                    try:
                        inp = InvestigationInput(case_id=cid, question=case.public.question,
                                                 request=case.public.request, graph=case.graph, record=case.record,
                                                 spec=validation_spec(cid))
                        provider = RuleBaselineProvider() if arm == "baseline" else MockProvider()
                        out = run_investigation(inp, _config(cid, arm), provider, output / "investigations",
                                                cache_dir=None, input_ref={"kind": "validation", "case_id": cid},
                                                run_prefix=label + "-",
                                                reproduce=f"uv run --frozen blackgrid sprint4 --protocol {protocol} --output NEW_DIRECTORY")
                        item = {"case": cid, "arm": arm, "path": str(out.run_dir.relative_to(output)),
                                "elapsed_s": time.perf_counter() - before,
                                "config_sha256": canonical_sha256(_config(cid, arm))}
                        pairs.append(item)
                        append(attempts, {"attempt": label, "state": "finished", **item,
                                          "status": out.outcome.status})
                        print(f"{label}: {out.outcome.status}", flush=True)
                    except Exception as exc:
                        error = {"attempt": label, "state": "failed", "error": type(exc).__name__ + ": " + str(exc)[:300]}
                        errors.append(error)
                        append(attempts, error)
                        print(f"{label}: failed ({type(exc).__name__})", flush=True)
            save(output / "agent_runs.json", pairs)
            guard()
            # Evaluator-only expectations are written after every investigation has finished.
            save(output / "evaluator_private/expectations.json",
                 [expectation(c, case_index(c)) for c in case_ids])
            pairs_of = (("validated", "tool_only"), ("validated", "baseline"))
            primary = _score(output, pairs, errors, attempts, False, case_ids)
            sensitivity = _score(output, pairs, errors, attempts, True, case_ids)
            save(output / "evaluation.json", {
                "version": EVALUATOR_VERSION, "protocol": protocol, "expected_case_arms": len(case_ids) * len(ARMS),
                "primary": {"rows": primary, "summary": summarize(primary, ARMS, pairs_of)},
                "sensitivity_preregistered_wording_accepted": {"rows": sensitivity,
                                                               "summary": summarize(sensitivity, ARMS, pairs_of)},
                "errors": errors})
            status = "completed" if not errors and len(pairs) == len(case_ids) * len(ARMS) else "partial"
    except Exception as exc:
        errors.append({"phase": "suite", "error": type(exc).__name__ + ": " + str(exc)[:300]})
        append(attempts, {"state": "failed", **errors[-1]})
        status = "failed"
    except BaseException as exc:  # interrupted: never left as "running" (R5)
        errors.append({"phase": "suite", "error": type(exc).__name__ + ": " + (str(exc)[:300] or "interrupted"),
                       "resumable": False, "note": "rerun the suite in a NEW output directory"})
        append(attempts, {"state": "interrupted", **errors[-1]})
        status = "interrupted"
        raise
    finally:
        save(output / "suite.json", {"suite": suite_version, "protocol": protocol, "status": status,
                                     "finished_utc": datetime.now(UTC).isoformat(),
                                     "elapsed_s": time.perf_counter() - started, "agent_runs": len(pairs),
                                     "errors": errors, "llm_mode": "mock", "paid_cost_usd": 0,
                                     "human_review": "waived by the user (D-059); AI reviewer only",
                                     "artifacts": {p.relative_to(output).as_posix(): sha(p) for p in output.rglob("*")
                                                   if p.is_file() and "investigations" not in p.relative_to(output).parts
                                                   and p.name != "suite.json"}})
    return output


def export_summary(output: Path, destination: Path) -> Path:
    """Minimized synthetic aggregates for version control (no run folders, no graphs)."""
    evaluation = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
    suite = json.loads((output / "suite.json").read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)
    summary = {"suite": suite["suite"], "status": suite["status"], "elapsed_s": suite["elapsed_s"],
               "errors": suite["errors"], "paid_cost_usd": 0, "evaluator": evaluation["version"],
               "primary": evaluation["primary"]["summary"],
               "sensitivity_preregistered_wording_accepted":
                   evaluation["sensitivity_preregistered_wording_accepted"]["summary"],
               "freeze_sha256": sha(output / "freeze.json"),
               "overlap_check": json.loads((output / "overlap_check.json").read_text(encoding="utf-8"))
               if (output / "overlap_check.json").is_file() else None}
    path = destination / "summary.json"
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (destination / "MANIFEST.json").write_text(json.dumps(
        {"summary.json": hashlib.sha256(path.read_bytes()).hexdigest(), "source_run": output.name}, indent=2) + "\n",
        encoding="utf-8")
    return path
