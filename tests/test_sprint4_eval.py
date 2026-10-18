"""Sprint 4 Session 6 pieces on development fixtures only; no s4 case outcome is generated here."""

from __future__ import annotations

import pytest

from blackgrid.evaluation import assess_claim
from blackgrid.providers import MockProvider
from blackgrid.sprint4 import RuleBaselineProvider, assess_claim_s4
from blackgrid.validation import CASE_IDS, S4_CASE_IDS, case_index, generator_seed, validation_spec

P = "experiment_report.json#/primary/result/"


def docs(p=0.01, verdict="supported", q=0.5, mean=0.4):
    nulls = [mean] * 99
    report = {"primary": {"suitable": True, "delta_q": q - mean, "null_values": nulls,
                          "result": {"observed_statistic": q, "null": {"mean": mean}, "p_value": p,
                                     "null_replicates": 99, "exceedances": 0 if q > mean else 99}},
              "secondary": None, "profile": {"components": 1, "isolated_nodes": 0}, "unknown_pairs": 0,
              "verdict": verdict}
    return {"experiment_report.json": report}


def claim(text, *fields):
    return {"text": text, "evidence_level": "descriptive", "evidence": list(fields)}


def test_s4_ids_seeds_and_specs_are_disjoint_from_sprint3():
    assert not set(S4_CASE_IDS) & set(CASE_IDS)
    s3 = {generator_seed(c) + k for c in CASE_IDS for k in range(4)}
    s4 = {generator_seed(c) + k for c in S4_CASE_IDS for k in range(4)}
    assert not s3 & s4 and all(1_000 <= s < 10_000 for s in s4)
    assert [case_index(c) for c in S4_CASE_IDS] == list(range(1, 25))
    assert validation_spec("val-101").seed == 40_001 and validation_spec("val-001").seed == 30_001


def test_preregistered_wording_is_the_only_primary_sensitivity_difference():
    d = docs()
    text = claim("Under the preregistered rule the verdict is 'supported' for this graph only.",
                 "experiment_report.json#/verdict")
    assert assess_claim_s4(text, d)[0] == "unsupported"
    assert assess_claim_s4(text, d, preregistered_ok=True) == assess_claim(text, d)
    saved = claim("The saved decision-rule verdict is 'supported' for this graph only.", "experiment_report.json#/verdict")
    assert assess_claim_s4(saved, d)[0] == "supported"
    assert assess_claim_s4(claim(saved["text"]), d)[0] == "unsupported"  # verdict field not cited


@pytest.mark.parametrize("p,fields,expected", [
    (0.01, ("observed_statistic", "null/mean", "p_value"), "supported"),
    (0.01, ("null/mean", "p_value"), "unsupported"),  # one-sided
    (0.55, ("observed_statistic", "null/mean", "p_value"), "unsupported"),  # literal but misleading
])
def test_comparisons_need_both_sides_and_a_significant_test(p, fields, expected):
    d = docs(p=p)
    c = claim(f"Observed modularity exceeds the null mean of 0.400 (p = {p:.3f}).", *(P + f for f in fields))
    assert assess_claim_s4(c, d)[0] == expected


def test_unknown_prose_stays_unassessed():
    assert assess_claim_s4(claim("Groups look tidy.", P + "p_value"), docs())[0] == "unassessed"


@pytest.mark.parametrize("request_,decision", [({"method": "auto"}, "run"), ({"method": "exec_python"}, "refuse"),
                                               ({"claim_type": "causal"}, "refuse")])
def test_rule_baseline_plans_by_fixed_rules(request_, decision):
    assert RuleBaselineProvider._plan({"task": {"request": request_}})["decision"] == decision
    assert RuleBaselineProvider.model != MockProvider.model


def test_rule_baseline_claims_are_templated_from_evidence():
    payload = {"evidence": {f"experiment_report.json#/primary/result/{k}": v for k, v in
                            (("observed_statistic", 0.5), ("null/mean", 0.4), ("p_value", 0.01))}
               | {"experiment_report.json#/verdict": "supported"}, "flags": ["degree_confound"]}
    out = RuleBaselineProvider._analyse(payload, revise=False)
    assert out["verdict"] == "supported" and out["flags"] == ["degree_confound"]
    assert [c["text"] for c in out["claims"]] == [
        "Modularity Q = 0.500 versus a degree-preserving null mean of 0.400 (p = 0.010).",
        "The saved decision-rule verdict is 'supported' for this graph only."]
