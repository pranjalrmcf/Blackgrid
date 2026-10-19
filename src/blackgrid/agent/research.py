"""Aggregate-only mock research tool facade bound to a verified Sprint 7 run.

The numerical controller executes registered experiments. This interface inspects
its evidence; an LLM cannot submit outcomes, paths, utilities, priors or code.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Literal

from blackgrid.contracts import Contract


class ResearchRequest(Contract):
    tool: Literal["reliability_audit", "belief_update", "experiment_decision", "causal_identification_check"]
    # No payload channel for invented evidence or arbitrary experiment definitions.


class ResearchTools:
    def __init__(self, output: Path, expected_manifest: str | None = None):
        self.output = output
        self.expected_manifest = expected_manifest

    def call(self, raw: dict) -> dict:
        request = ResearchRequest.model_validate(raw)
        if self.expected_manifest is not None:
            manifest = self.output / "sprint7_manifest.json"
            if not manifest.is_file() or hashlib.sha256(manifest.read_bytes()).hexdigest() != self.expected_manifest:
                raise ValueError("bound research evidence changed or is unavailable")
        from blackgrid.evaluation.sprint7 import verify
        verify(self.output)
        def read(name):
            return json.loads((self.output / name).read_text(encoding="utf-8"))
        if request.tool == "reliability_audit":
            r = read("reliability.json")
            return {"evidence": "reliability.json", "graphs": r["graphs"],
                    "paired_brier": r["paired_test_brier"], "real_data_interval": r["real_data_interval"],
                    "probability_display": False,
                    "bootstrap_confidence_lower": r["paired_test_brier"]["interval"][0],
                    "bootstrap_confidence_upper": r["paired_test_brier"]["interval"][1],
                    "scope": "saved synthetic temporal-graph demonstration; not real-data calibration"}
        if request.tool == "belief_update":
            # Reconstruct from deduplicated trusted receipts; never update from text.
            beliefs = read("beliefs.json")
            for method in beliefs["methods"].values():
                method["credible_lower"], method["credible_upper"] = method["credible_interval_95"]
            return {"evidence": "beliefs.json", **beliefs}
        if request.tool == "experiment_decision":
            r = read("decisions.json")
            decision = r["trace"][-1]
            stable = r["sensitivity"]["stable_action"] and r["sensitivity"]["stable_terminal"]
            return {"evidence": "decisions.json", "decision": decision if stable else None,
                    "candidates": {c["action"]: c for c in decision["candidates"]} if stable else {},
                    "abstention": None if stable else "unstable recommendation under registered sensitivity",
                    "real_forecast_voi": r["real_forecast_voi"]}
        c = read("causal.json")
        return {"evidence": "causal.json", "synthetic": c["gate"], "real": c["collegemsg"]}


def workflow_claims(evidence: dict) -> list[dict]:
    """Exact workflow claims; no free-form semantic judgments or real-world inference."""
    out = []
    def add(text, paths):
        if all(p in evidence for p in paths):
            out.append({"text": text, "evidence_level": "descriptive", "evidence": paths})
    r = "reliability_audit.json#/"
    if r + "graphs" in evidence:
        add(f"The saved synthetic calibration study used {evidence[r+'graphs']} independent graphs; "
            "it does not validate probability display for real forecasts.", [r+"graphs", r+"probability_display", r+"scope"])
        add(f"The synthetic paired Brier bootstrap confidence interval is "
            f"[{evidence[r+'bootstrap_confidence_lower']:.6f}, {evidence[r+'bootstrap_confidence_upper']:.6f}].",
            [r+"bootstrap_confidence_lower", r+"bootstrap_confidence_upper", r+"paired_brier/interval_type"])
    b = "belief_update.json#/methods/A/"
    if b + "mean" in evidence:
        add(f"Under the registered synthetic Beta model, method A has posterior mean {evidence[b+'mean']:.4f} "
            f"and a credible interval [{evidence[b+'credible_lower']:.4f}, {evidence[b+'credible_upper']:.4f}].",
            [b+"mean", b+"credible_lower", b+"credible_upper", "belief_update.json#/target"])
    d = "experiment_decision.json#/"
    if evidence.get(d + "abstention"):
        add("The saved synthetic experiment recommendation is withheld because it changes under the registered sensitivity checks.",
            [d+"abstention"])
    elif d+"decision/action" in evidence:
        add(f"The saved synthetic loop's next action is '{evidence[d+'decision/action']}' under its registered utility; "
            "value of information for real forecasts is unavailable.", [d+"decision/action", d+"real_forecast_voi"])
        cost, reason = d+"decision/objective/cost", d+"decision/reason"
        if cost in evidence and reason in evidence:
            add(f"The saved synthetic objective charges {evidence[cost]:.4f} utility units per experiment; "
                f"the decision rationale is '{evidence[reason]}'.", [cost, reason])
        for path in sorted(evidence):
            if path.startswith(d+"candidates/") and path.endswith("/net_value"):
                base = path.removesuffix("net_value")
                if base+"action" in evidence and base+"evsi" in evidence:
                    add(f"Saved synthetic action {evidence[base+'action']} has expected value of sample information "
                        f"{evidence[base+'evsi']:.4f} and net value {evidence[path]:.4f} in registered utility units.",
                        [base+"action", base+"evsi", path])
    c = "causal_identification_check.json#/"
    if c+"real/verdict" in evidence:
        add("The registered causal example supports simulated intervention only; CollegeMsg causal effects are not identified.",
            [c+"synthetic/verdict", c+"real/verdict", c+"synthetic/limitation"])
        review = c+"synthetic/review/"
        fields = ("estimand", "treatment", "outcome", "unit")
        if all(review+f in evidence for f in fields):
            add(f"The saved synthetic estimand is {evidence[review+'estimand']}: treatment "
                f"{evidence[review+'treatment']} on outcome {evidence[review+'outcome']}, with unit "
                f"'{evidence[review+'unit']}'.", [review+f for f in fields])
        assumptions = ("consistency", "positivity", "no_hidden_confounding", "no_interference",
                       "no_selection_bias", "measurement_valid", "time_order")
        if all(review+f in evidence for f in assumptions):
            add("The synthetic review records " + "; ".join(f"{f}={evidence[review+f]}" for f in assumptions)
                + ". These are supplied assumptions, not empirically verified facts.",
                [review+f for f in assumptions] + [c+"synthetic/limitation"])
        adjustment = sorted(p for p in evidence if p.startswith(review+"adjustment/"))
        if adjustment:
            add("The saved synthetic adjustment set is " + ", ".join(str(evidence[p]) for p in adjustment)
                + "; the checker validates DAG syntax and the supported backdoor criterion only.",
                adjustment + [c+"synthetic/limitation"])
    return out


def checked_claim(kind: str, value: object, evidence: dict) -> dict:
    """Closed claim vocabulary, exact value binding; no semantic verification claim."""
    definitions = {
        "posterior_mean_A": ("beliefs.json", ("methods", "A", "mean"), "Bayesian synthetic success rate"),
        "next_action": ("decisions.json", ("trace", -1, "action"), "simulated research action"),
        "brier_interval": ("reliability.json", ("paired_test_brier", "interval"), "bootstrap confidence interval"),
        "causal_verdict": ("causal.json", ("gate", "verdict"), "synthetic causal gate"),
    }
    if kind not in definitions:
        raise ValueError("unregistered claim; probabilities, causal prose and interval relabeling rejected")
    artifact, path, label = definitions[kind]
    actual = evidence[artifact]
    for key in path:
        actual = actual[key]
    if actual != value:
        raise ValueError("claim disagrees with evidence")
    return {"kind": kind, "value": value, "interpretation": label,
            "evidence": artifact + "#/" + "/".join(map(str, path)), "scope": "registered synthetic model only"}
