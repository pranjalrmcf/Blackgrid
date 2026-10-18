"""critic-v5 (D-065): the five label/citation mistakes found in the live-pilot review, plus controls.

The five regressions are the reviewed live claims (synthetic data). Controls check that correct
forms of the same statements stay expressible.
"""

from __future__ import annotations

import pytest

from blackgrid.agent import flatten
from blackgrid.critic import CriticContext, critique

P = "experiment_report.json#/primary/"
S = "experiment_report.json#/secondary/"
E = {P + "result/observed_statistic": 0.5611705641432158, P + "result/p_value": 0.01, P + "delta_q": 0.267,
     P + "result/null/mean": 0.29420042678068836, P + "result/null/q95": 0.32062359624785314,
     P + "result/null/q05": 0.27, P + "result/null/q50": 0.412, P + "result/null/sd": 0.014,
     S + "result/observed_statistic": 0.3757, S + "result/p_value": 0.22, S + "z": 0.7188,
     "experiment_report.json#/verdict": "not_supported", "experiment_report.json#/raw_verdict": "not_supported",
     "experiment_report.json#/flags/0": "degree_confound",
     "experiment_report.json#/profile/components": 4, "experiment_report.json#/profile/degree_max": 30,
     "experiment_report.json#/profile/degree_median": 4.0}
CTX = CriticContext(evidence=E, verdict="not_supported", delta_q=0.267, p_value=0.01, alpha=0.05)


def check(text, *links):
    return critique({"text": text, "evidence_level": "descriptive", "evidence": list(links)}, CTX)


@pytest.mark.parametrize("text,links,rule", [
    ("Observed delta_q was 0.5611705641432158; p_value 0.01; null mean 0.29420042678068836.",
     (P + "result/observed_statistic", P + "result/p_value", P + "result/null/mean"), "R3"),  # live-039
    ("Secondary largest_component analysis verdict was not_supported; observed statistic 0.3757, p=0.22, z=0.7188.",
     ("experiment_report.json#/verdict", S + "result/observed_statistic", S + "result/p_value", S + "z"),
     "R10"),  # live-041
    ("Flag degree_confound applies; saved and raw verdicts are not_supported.",
     ("experiment_report.json#/verdict", "experiment_report.json#/raw_verdict"), "R11"),  # live-063
    ("Null distribution: mean 0.294, sd 0.014; observed 0.561 is within the null range.",
     (P + "result/null/mean", P + "result/null/sd", P + "result/observed_statistic"), "R12"),  # live-011 form
    ("Primary delta Q 0.267 vs null mean 0.294 (q95 0.321).",
     (P + "delta_q", P + "result/null/mean", P + "result/null/q95"), "R13"),  # live-015 form
])
def test_the_five_reviewed_mistakes_are_rejected(text, links, rule):
    decision = check(text, *links)
    assert not decision.accepted and any(r.startswith(rule) for r in decision.reasons), decision.reasons


@pytest.mark.parametrize("text,links", [
    ("Observed delta_q was 0.267; observed_statistic 0.561.", (P + "delta_q", P + "result/observed_statistic")),
    ("Secondary largest_component analysis: observed statistic 0.3757, p=0.22; the overall verdict is not_supported.",
     (S + "result/observed_statistic", S + "result/p_value", "experiment_report.json#/verdict")),
    ("Flag degree_confound applies.", ("experiment_report.json#/flags/0",)),
    ("The degree_confound flag applies: max degree 30 vs median 4.0.",
     ("experiment_report.json#/profile/degree_max", "experiment_report.json#/profile/degree_median")),
    ("Flag: disconnected (4 components).", ("experiment_report.json#/profile/components",)),
    ("No degree_confound flag was raised.", ("experiment_report.json#/verdict",)),
    ("Observed 0.561 lies outside the null range (q05 0.27, q95 0.321).",
     (P + "result/observed_statistic", P + "result/null/q05", P + "result/null/q95")),
    ("Observed Q 0.561 vs null mean 0.294; delta Q 0.267.",
     (P + "result/observed_statistic", P + "result/null/mean", P + "delta_q")),
    ("Null median 0.412, q95 0.321.", (P + "result/null/q50", P + "result/null/q95")),
])
def test_correct_forms_stay_expressible(text, links):
    decision = check(text, *links)
    assert decision.accepted, decision.reasons


def test_secondary_numbers_must_bind_to_secondary_fields():
    wrong = check("Secondary analysis: observed statistic 0.561.", P + "result/observed_statistic",
                  S + "result/observed_statistic")
    assert not wrong.accepted and any(r.startswith("R3") for r in wrong.reasons)


def test_flags_are_citable_evidence_paths():
    flat = flatten({"experiment_report.json": {"flags": ["disconnected", "degree_confound"], "values": [0.1, 0.2]}})
    assert flat["experiment_report.json#/flags/1"] == "degree_confound"
    assert not any(k.startswith("experiment_report.json#/values") for k in flat)  # numeric lists stay out of prompts
