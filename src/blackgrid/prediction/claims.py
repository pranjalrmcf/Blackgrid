"""Predictive-claim checker `pred-critic-v1` (SPRINT_06.md §8). Separate from the community critic.

Each claim carries a `scope` naming task, cutoff, horizon, candidate policy, split and method, and
cites artifact paths. Rules:
  P1 scope      task, cutoff, horizon, candidate_policy, split and method are all present and match
                the forecast being reported
  P2 evidence   at least one cited path, every cited path exists, every number equals a cited value
  P3 metric     a metric name in the text (AP, precision, recall, AUC) needs a cited field of that metric
  P4 language   no probability/chance/calibrated wording; no causal or influence wording; no
                significance or generalization wording
  P5 cold start no claim about predicting new or unseen people (the task is known-node only)
"""
from __future__ import annotations

import re

from blackgrid.agent.critic import CAUSAL, unsupported_numbers

PRED_CRITIC_VERSION = "pred-critic-v1"
SCOPE_KEYS = ("task", "cutoff", "horizon_s", "candidate_policy", "split", "method")
PROBABILITY = re.compile(r"\b(probabilit\w*|chance|odds|calibrat\w*|certain(ly)?|guarantee\w*)\b|\d+(\.\d+)?\s*%\s*"
                         r"(likely|chance|probability)", re.I)
INFLUENCE = re.compile(r"\b(influenc\w*|persuad\w*|recommend\w*|should (message|contact))\b", re.I)
OVERREACH = re.compile(r"\b(significan\w*|generali[sz]\w*|all (colleges|networks|students)|proves?)\b", re.I)
COLD_START = re.compile(r"\b(new (users?|people|students|nodes?|members?)|newcomers?|unseen (nodes?|people|users?)|"
                        r"cold[- ]start)\b", re.I)
NEGATED = re.compile(r"\b(not|no|never|excluded|exclude[sd]?|cannot|without)\b", re.I)
METRICS = {"average precision": ("average_precision", "ap_difference"), "AP": ("average_precision", "ap_difference"),
           "precision@": ("precision_at_k",), "recall@": ("recall_at_k",), "AUC": ("roc_auc",)}


def check(claim: dict, evidence: dict[str, object], scope: dict) -> list[str]:
    """Return rejection reasons (empty = accepted)."""
    reasons: list[str] = []
    text = str(claim.get("text", ""))
    given = claim.get("scope") or {}
    missing = [k for k in SCOPE_KEYS if k not in given]
    if missing:
        reasons.append(f"P1: claim scope is missing {missing}")
    wrong = [k for k in SCOPE_KEYS if k in given and given[k] != scope.get(k)]
    if wrong:
        reasons.append(f"P1: claim scope disagrees with the forecast on {wrong}")
    links = claim.get("evidence") or []
    if not links:
        reasons.append("P2: no cited evidence")
    absent = [x for x in links if x not in evidence]
    if absent:
        reasons.append(f"P2: cited evidence not found: {absent[:3]}")
    cited = {x: evidence[x] for x in links if x in evidence}
    bad = unsupported_numbers(text, list(cited.values()))
    if bad:
        reasons.append(f"P2: numbers not matching cited evidence: {bad[:5]}")
    for word, field in METRICS.items():
        pattern = re.escape(word) if not word.isalpha() else rf"\b{re.escape(word)}\b"
        if re.search(pattern, text, re.I if word.islower() else 0) and not any(p.endswith(field) for p in cited):
            reasons.append(f"P3: mentions {word.strip('@')} without citing a {field[0]} field")
    if PROBABILITY.search(text):
        reasons.append("P4: scores are uncalibrated rankings; no probability, chance or calibration wording")
    if CAUSAL.search(text) or INFLUENCE.search(text):
        reasons.append("P4: no causal, influence or recommendation wording for an associational forecast")
    if OVERREACH.search(text):
        reasons.append("P4: no significance, proof or generalization claim from two held-out windows of one network")
    for m in COLD_START.finditer(text):
        start = max(text.rfind(";", 0, m.start()), text.rfind(".", 0, m.start() - 1)) + 1
        ends = [i for i in (text.find(";", m.end()), text.find(". ", m.end())) if i != -1]
        clause = text[start: min(ends) if ends else len(text)]
        if not NEGATED.search(clause):  # stating the exclusion ("... are excluded") is allowed
            reasons.append("P5: the forecast covers known nodes only; it says nothing about new or unseen people")
            break
    return reasons
