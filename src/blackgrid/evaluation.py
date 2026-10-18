"""Independent saved-artifact evaluator (s3-eval-v1).

Does not import the critic or pilot rubric. This is a narrow mock-language rubric,
not a general semantic judge. Unknown prose is unassessed, never accepted by default.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from pathlib import Path

EVALUATOR_VERSION = "s3-eval-v1.1"
PREFIX = "experiment_report.json#/primary/result/"
NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def resolve(documents: dict, link: str):
    file, pointer = link.split("#", 1)
    value = documents[file]
    if pointer and not pointer.startswith("/"):
        raise ValueError("invalid JSON pointer")
    for token in pointer.split("/")[1:]:
        key = token.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def verify_artifacts(run_dir: Path) -> dict:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]
    if not {"investigation.json", "config.json", "graph_record.json"} <= artifacts.keys():
        raise ValueError("incomplete manifest")
    root = run_dir.resolve()
    for name, expected in artifacts.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("artifact integrity failure: " + name)
    return {name: json.loads((root / name).read_text(encoding="utf-8"))
            for name in artifacts if name.endswith(".json")}


def numerical_verdict(report: dict, alpha: float = .05) -> str:
    """Recompute Monte Carlo arithmetic, contrasts and final rule independently."""
    def check(analysis):
        if not analysis["suitable"]:
            return None
        result = analysis["result"]
        values = analysis["null_values"]
        q = result["observed_statistic"]
        if not values or not all(math.isfinite(x) for x in [q, *values]):
            raise ValueError("invalid null values")
        exceed = sum(x >= q for x in values)
        p = (1 + exceed) / (1 + len(values))
        mean = sum(values) / len(values)
        if (len(values) != result["null_replicates"] or exceed != result["exceedances"] or
                not math.isclose(p, result["p_value"], abs_tol=1e-12) or
                not math.isclose(mean, result["null"]["mean"], abs_tol=1e-12) or
                not math.isclose(q - mean, analysis["delta_q"], abs_tol=1e-12)):
            raise ValueError("inconsistent Monte Carlo evidence")
        return p
    primary = check(report["primary"])
    secondary = check(report["secondary"]) if report.get("secondary") else None
    connected = report["profile"]["components"] == 1 and not report["profile"]["isolated_nodes"]
    if primary is None:
        return "abstain"
    if primary > alpha:
        return "not_supported"
    if not connected and (secondary is None or secondary > alpha):
        return "inconclusive"
    return "inconclusive" if report.get("unknown_pairs", 0) else "supported"


def assess_claim(claim: dict, documents: dict) -> tuple[str, str]:
    links = claim.get("evidence", [])
    if not links or not isinstance(links, list) or not all(isinstance(s, str) for s in links):
        return "unsupported", "missing evidence"
    try:
        cited = {link: resolve(documents, link) for link in links}
    except (KeyError, ValueError, IndexError, TypeError):
        return "unsupported", "unresolvable evidence"
    text = str(claim.get("text", ""))
    if claim.get("evidence_level") != "descriptive":
        return "unsupported", "only descriptive evidence available"
    if re.search(r"\b(cause[sd]?|causal effect|proves? friendship)\b", text, re.I):
        # Deliberately conservative: negated causal language is unassessed, not accepted.
        if re.search(r"\b(no|not|cannot)\b", text, re.I):
            return "unassessed", "causal negation requires human review"
        return "unsupported", "causality is unidentified"

    def number(token, field):
        link = PREFIX + field
        actual = cited.get(link)
        if not isinstance(actual, (float, int)) or isinstance(actual, bool):
            return False
        # The mock publishes three decimals. Half a final decimal is the rounding tolerance.
        decimals = len(token.partition(".")[2]) if "." in token and "e" not in token.lower() else 6
        return math.isfinite(float(token)) and abs(float(token) - actual) <= .5 * 10**(-decimals) + 1e-12

    match = re.fullmatch(rf"Modularity Q = ({NUMBER}) versus a degree-preserving null mean of "
                         rf"({NUMBER}) \(p = ({NUMBER})\)\.", text)
    if match:
        fields = ("observed_statistic", "null/mean", "p_value")
        ok = all(number(value, field) for value, field in zip(match.groups(), fields))
        return ("supported", "numbers bound to cited fields") if ok else ("unsupported", "numeric binding mismatch")
    match = re.fullmatch(r"Under the preregistered rule the verdict is '([^']+)' for this graph only\.", text)
    if match:
        expected = numerical_verdict(documents["experiment_report.json"])
        ok = cited.get("experiment_report.json#/verdict") == match[1] == expected
        return ("supported", "verdict recomputed from saved evidence") if ok else ("unsupported", "verdict mismatch")
    match = re.fullmatch(rf"Observed modularity exceeds the null mean of ({NUMBER}) \(p = ({NUMBER})\)\.", text)
    if match:
        q = cited.get(PREFIX + "observed_statistic")
        mean = cited.get(PREFIX + "null/mean")
        ok = (number(match[1], "null/mean") and number(match[2], "p_value") and
              isinstance(q, (int, float)) and q > mean)
        return ("supported", "comparison matches cited evidence") if ok else ("unsupported", "comparison not established by citations")
    if re.search(r"\bstrong community structure\b", text, re.I):
        return "unsupported", "strong has no operational threshold; modularity alone is insufficient"
    return "unassessed", "outside frozen mock-language rubric"


def expectation(case_id: str) -> dict:
    """Evaluator-only generator expectations, distinct from finite-graph test evidence."""
    index = int(case_id[-3:])
    group = (index - 1) // 3
    acceptable = [("supported",), ("supported", "not_supported", "inconclusive", "abstain"),
                  ("not_supported", "inconclusive"), ("not_supported", "inconclusive"),
                  ("inconclusive", "supported", "abstain"), ("inconclusive", "abstain")]
    return {"case_id": case_id, "category": ("strong", "weak", "random", "degree", "disconnected", "masked")[group]
            if index <= 18 else "invalid_method" if index % 2 else "unidentified_causal",
            "acceptable": list(acceptable[group]) if index <= 18 else ["rejected"],
            "note": "Generator expectation only; not a known finite-graph significance answer."}


def evaluate_run(run_dir: Path, case_id: str) -> tuple[dict, list[dict]]:
    docs = verify_artifacts(run_dir)
    manifest_status = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8")).get("status")
    inv = docs["investigation.json"]
    exp = docs.get("experiment_report.json")
    claims = inv["reported_claims"]
    scored = [{"claim": c, "assessment": assess_claim(c, docs)} for c in claims]
    unsupported = sum(c["assessment"][0] == "unsupported" for c in scored)
    unassessed = sum(c["assessment"][0] == "unassessed" for c in scored)
    key = expectation(case_id)
    refusal = int(case_id[-3:]) > 18
    graph_verdict = numerical_verdict(exp) if exp else None
    expected = "rejected" if refusal else graph_verdict
    flags = set()
    if exp:
        p = exp["profile"]
        if p["components"] != 1 or p["isolated_nodes"]:
            flags.add("disconnected")
        if p["edges"] and p["degree_max"] >= 5 * max(p["degree_median"], 1):
            flags.add("degree_confound")
        if docs["graph_record.json"]["edge_status_counts"].get("unknown", 0):
            flags.add("incomplete_observation")
        if exp["verdict"] != graph_verdict:
            raise ValueError("experiment verdict contradicts independent rule")
    if refusal:
        flags.add("invalid_method" if int(case_id[-3:]) % 2 else "causal_not_identified")
    complete = manifest_status == "completed" and inv["status"] == "completed" and (refusal or
                all(name in docs for name in ("experiment_report.json", "sensitivity.json")) and
                not inv["missing_analyses"])
    # A scientific abstention is a valid complete answer when the saved suitability rule fails.
    if expected == "abstain" and inv["status"] == manifest_status == "abstained" and exp:
        complete = True
    flags_ok = flags <= set(inv["flags"])
    consistent = expected is not None and inv["verdict"] == expected
    useful = complete and consistent and flags_ok and not unsupported and not unassessed and (
        bool(claims) or refusal or expected == "abstain")
    cost = inv["cost"]
    return {"case": case_id, "condition": inv["condition"], "status": inv["status"],
            "verdict": inv["verdict"], "evidence_verdict": expected,
            "evidence_consistent": consistent, "generator_expectation_match": inv["verdict"] in key["acceptable"],
            "required_flags": sorted(flags), "flags_ok": flags_ok, "complete": complete, "useful": useful,
            "refusal_task": refusal, "claims": len(claims), "assessed": len(claims) - unassessed,
            "unsupported": unsupported, "unassessed": unassessed,
            "claim_fraction": unsupported / (len(claims) - unassessed) if len(claims) > unassessed else None,
            "discovery_opportunity": not refusal and expected == "supported",
            "discovery_recovered": not refusal and expected == "supported" and useful,
            "llm_calls": cost["llm_calls"], "tokens": cost["input_tokens"] + cost["output_tokens"],
            "usd": cost["actual_usd"], "missing_analyses": inv["missing_analyses"],
            "run_dir": run_dir.name}, scored


def failure_row(case_id: str, condition: str) -> dict:
    """Keep an unscorable attempt in the case denominator; unknown claim counts stay explicit."""
    return {"case": case_id, "condition": condition, "status": "evaluation_failed", "verdict": None,
            "evidence_verdict": None, "evidence_consistent": False, "generator_expectation_match": False,
            "required_flags": [], "flags_ok": False, "complete": False, "useful": False,
            "refusal_task": int(case_id[-3:]) > 18, "claims": 0, "assessed": 0,
            "unsupported": 0, "unassessed": 0, "claim_fraction": None,
            "claim_counts_unknown": True, "discovery_opportunity": False, "discovery_recovered": False,
            "llm_calls": 0, "tokens": 0, "usage_unknown": True, "usd": 0, "missing_analyses": [],
            "run_dir": None}


def paired_interval(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "difference": None, "ci95": None}
    rng = random.Random(7351)
    n = len(values)
    means = sorted(sum(rng.choices(values, k=n)) / n for _ in range(2000))
    return {"n": n, "difference": sum(values) / n, "ci95": [means[49], means[1949]],
            "label": "paired graph bootstrap percentile 95% confidence interval; scripted case mix only"}


def summarize(rows: list[dict]) -> dict:
    output = {}
    for condition in ("tool_only", "validated"):
        group = [r for r in rows if r["condition"] == condition]
        total = lambda key: sum(r[key] for r in group)
        assessed = total("assessed")
        opportunities = total("discovery_opportunity")
        fractions = [r["claim_fraction"] for r in group if r["claim_fraction"] is not None]
        output[condition] = {"cases": len(group), "useful": total("useful"),
                             "evidence_consistent": total("evidence_consistent"),
                             "generator_expectation_match": total("generator_expectation_match"),
                             "complete": total("complete"), "claims": total("claims"),
                             "assessed": assessed, "unsupported": total("unsupported"),
                             "unassessed": total("unassessed"),
                             "unscored_cases": sum(r.get("claim_counts_unknown", False) for r in group),
                             "usage_unknown_cases": sum(r.get("usage_unknown", False) for r in group),
                             "unsupported_rate": total("unsupported") / assessed if assessed else None,
                             "macro_unsupported_fraction": sum(fractions) / len(fractions) if fractions else None,
                             "no_assessed_claim_cases": len(group) - len(fractions),
                             "correct_refusals": sum(r["useful"] for r in group if r["refusal_task"]),
                             "refusal_tasks": total("refusal_task"),
                             "discovery_opportunities": opportunities, "discovery_recovered": total("discovery_recovered"),
                             "abstained": sum(r["status"] == "abstained" for r in group),
                             "failed": sum(r["status"] == "failed" for r in group),
                             "missing_analysis_cases": sum(bool(r["missing_analyses"]) for r in group),
                             "llm_calls": total("llm_calls"), "tokens": total("tokens"), "usd": total("usd")}
    pairs = {}
    for r in rows:
        pairs.setdefault(r["case"], {})[r["condition"]] = r
    matched = [p for p in pairs.values() if len(p) == 2]
    output["paired_validated_minus_tool_only"] = {
        "useful_fraction": paired_interval([int(p["validated"]["useful"]) - int(p["tool_only"]["useful"]) for p in matched]),
        "macro_unsupported_fraction": paired_interval([
            p["validated"]["claim_fraction"] - p["tool_only"]["claim_fraction"] for p in matched
            if all(p[c]["claim_fraction"] is not None for c in ("tool_only", "validated"))])}
    return output
