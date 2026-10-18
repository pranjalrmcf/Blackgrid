"""Deterministic plan validator and claim critic (Sprint 1 Day 9).

Rubric (version `critic-v1`), applied to every drafted claim:

  R1 schema        text present (<= 500 chars); known evidence level; evidence is a list of paths
  R2 evidence      factual claims cite >= 1 artifact path, and every cited path exists
  R3 numbers       every number equals a cited value at the displayed precision (x100 only when written
                   with '%'), and a labelled number (Q, p, z, null mean, sd, delta Q) matches a cited
                   field with that meaning
  R4 level         Sprint 1 tools support only `descriptive` (or `unsupported`) claims
  R5 causal        causal language is rejected: no estimand or identification argument exists
  R6 structure     "has community structure"-type wording needs verdict == supported
  R7 comparison    "exceeds / higher than" the null needs delta_q > 0 and p <= alpha, and the claim must
                   cite both sides: an observed value, a null-side value (null mean or delta Q), and the
                   test conclusion (p-value or verdict)  [v3]
  R8 strength      effect-strength adjectives ("strong", "weak", "substantial", "clear", "real groups", ...)
                   are rejected: a small p against a null is not an effect size, and no threshold for
                   such words is preregistered  [v3]
  R9 registration  a claim may not call a result "preregistered": no cited artifact establishes
                   registration (negated statements such as "not preregistered" are allowed)  [v4]
  R3 labels        v5: labels also match snake_case/hyphenated forms (delta_q, null_mean, p_value,
                   observed_statistic) and null quantiles/median (q05, q50, q95); a claim about the
                   secondary (largest-component) analysis must bind its labelled numbers to secondary fields
  R10 scope        a secondary/largest-component verdict cannot cite the overall verdict field (the
                   secondary analysis has no verdict of its own) unless the overall verdict is named  [v5]
  R11 flags        asserting a flag (degree_confound, incomplete_observation, "... flag") needs a cited
                   flag entry with that value  [v5]
  R12 range        "within / outside the null range" needs the cited null q05 and q95  [v5]
  R13 pairing      delta Q set against the null mean ("delta Q 0.27 vs null mean 0.48") compares a
                   difference with a score; compare observed Q with the null mean instead  [v5]

The critic is a rule set, not a model, and it is not independent scientific validation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from blackgrid.contracts import Contract, EvidenceLevel, NonEmpty
from blackgrid.analysis.experiment import DEGREE_CONFOUND_RATIO
from blackgrid.agent.tools import AnswerKeyAccess, ToolRejected, parse_request

# v2: no bare x100 matches; labelled numbers must match their field (D-038).
# v3: comparisons cite both sides; unoperationalized strength wording is rejected (Sprint 4 R4, D-057).
#     Provisional until the blinded human review (docs/sprint04_review_rubric.md) is complete.
# v4: R9 rejects unestablished "preregistered" wording (s4-v2, D-061).
# v5: label variants, secondary scope, flags, null range and delta/null pairing, from the live-pilot review
#     (D-064, D-065). Written after inspecting those claims: development evidence until fresh cases test it.
CRITIC_VERSION = "critic-v6 structural-v1"

CAUSAL = re.compile(r"\b(caus\w*|effects? of|drives?|driven by|leads? to|influenc\w*|impacts? of|because of|"
                    r"due to|results? in)\b", re.I)
STRUCTURE = re.compile(r"\b(community structure|communities exist|has communities|(strong|clear|distinct|real) "
                       r"(communit\w*|groups|clusters)|friend[- ]?groups|is (highly )?modular)\b", re.I)
COMPARATIVE = re.compile(r"\b(exceed\w*|higher than|greater than|larger than|stronger than|above the null)\b", re.I)
NEGATION = re.compile(r"\b(not|no|never|neither|nor|without|does ?n.t)\b(\W+\w+){0,3}\W*$", re.I)
STRENGTH = re.compile(r"\b(strong(ly)?|weak(ly)?|substantial(ly)?|pronounced|marked(ly)?|considerabl[ey]|"
                      r"dramatic(ally)?|very|highly|clear(ly)?|robust(ly)?|large|huge|massive|real|genuine|"
                      r"meaningful)\b(\W+\w+){0,3}?\W+(communit\w*|structure|groups?|clusters?|modular\w*|"
                      r"effects?|evidence|signal|differences?)\b", re.I)
REGISTERED = re.compile(r"\bpre-?registered\b", re.I)
SECONDARY = re.compile(r"\b(secondary|largest[\s_-]*component)\b", re.I)
OVERALL = re.compile(r"\b(overall|primary|whole[\s_-]*graph|saved)\b", re.I)
FLAG_NAMES = {"degree_confound": r"degree[\s_-]*confound", "incomplete_observation": r"incomplete[\s_-]*observation",
              "disconnected": r"disconnected(?=[\s_-]*flag)|flag\W+disconnected"}
NULL_RANGE = re.compile(r"\b(within|inside|outside|beyond)\s+(?:of\s+)?(?:the\s+)?null(?:'s)?[\s_-]*"
                        r"(range|distribution|interval|band|envelope)\b", re.I)
_CLAUSE = r"(?:(?!\.\s)[^;])"  # within one clause; decimal points are not sentence ends
PAIRING = re.compile(r"\bdelta[\s_-]*q\b" + _CLAUSE + r"{0,30}?\b(vs\.?|versus|compared (?:with|to)|against|"
                     r"relative to)" + _CLAUSE + r"{0,20}?\bnull[\s_-]*mean\b", re.I)
OBSERVED_SIDE = ("observed_statistic", "observed_q_min", "observed_q_max", "observed_q_median")
NULL_SIDE = ("null/mean", "delta_q", "delta_q_min", "delta_q_median", "delta_q_max")
CONCLUSION = ("p_value", "#/verdict", "/raw_verdict")
ISO_TIME = re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:\d{2})?)?")
NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?!\.?\d)(?![A-Za-z_])(%?)")
ALLOWED_LEVELS = {EvidenceLevel.DESCRIPTIVE, EvidenceLevel.UNSUPPORTED}


def numeric_tokens(text: str) -> list[tuple[str, bool]]:
    """Numbers in prose as (token, is_percent); ISO dates/times and identifiers are skipped."""
    cleaned = ISO_TIME.sub(" ", text.replace("−", "-"))
    return [(m.group(0).rstrip("%"), m.group(1) == "%") for m in NUMBER.finditer(cleaned)]


def number_matches(token: str, percent: bool, value: object) -> bool:
    """A bare number must equal the value; only a number written with '%' may equal value x 100."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    shown = float(token)
    decimals = len(token.split(".")[1]) if "." in token else 0
    candidate = value * 100 if percent else value
    return abs(round(candidate, decimals) - shown) < 1e-9


def unsupported_numbers(text: str, values: list[object]) -> list[str]:
    return [t + ("%" if p else "") for t, p in numeric_tokens(text) if not any(number_matches(t, p, v) for v in values)]


# A labelled number must match a cited field with that meaning, not just any cited value.
_NUM = r"\(?\s*(-?\d+(?:\.\d+)?)(?!\.?\d)(?![A-Za-z_%])"
_LINK = r"\s*(?:=|:|of|is|was)?\s*"
_SEP = r"[\s_-]*"  # v5: "delta Q", "delta_q", "delta-Q" are the same label
LABELS: tuple[tuple[str, re.Pattern, tuple[str, ...]], ...] = (
    ("delta Q", re.compile(r"\bdelta" + _SEP + r"Q(?![\w])" + _LINK + _NUM, re.I), ("delta_q",)),
    ("null mean", re.compile(r"\bnull" + _SEP + r"mean\b" + _LINK + _NUM, re.I), ("null/mean",)),
    ("null sd", re.compile(r"\b(?:null" + _SEP + r")?sd\b" + _LINK + _NUM, re.I), ("null/sd",)),
    ("null q05", re.compile(r"\b(?:null" + _SEP + r")?q05\b" + _LINK + _NUM, re.I), ("null/q05",)),
    ("null q95", re.compile(r"\b(?:null" + _SEP + r")?q95\b" + _LINK + _NUM, re.I), ("null/q95",)),
    ("median", re.compile(r"\b(?:null" + _SEP + r")?(?:q50|median)\b" + _LINK + _NUM, re.I),
     ("null/q50", "observed_q_median", "delta_q_median", "degree_median")),
    ("Q (observed modularity)",
     re.compile(r"(?<!delta )(?<!delta_)(?<!delta)\b(?:[Mm]odularity(?:\s+Q)?|Q|observed" + _SEP +
                r"(?:statistic|Q|modularity))(?![\w])" + _LINK + _NUM),
     ("observed_statistic", "observed_q_min", "observed_q_max", "observed_q_median")),
    ("p-value", re.compile(r"\bp(?:" + _SEP + r"value)?(?![\w])" + _LINK + _NUM, re.I), ("p_value",)),
    ("z", re.compile(r"\bz(?![\w])" + _LINK + _NUM), ("/z",)),
)


def mislabelled_numbers(text: str, cited: dict[str, object]) -> list[str]:
    """Numbers attached to a known label (Q, p, z, null mean, ...) that match no cited field of that meaning.

    v5: when the claim is about the secondary analysis only, experiment fields must be secondary ones.
    """
    cleaned = ISO_TIME.sub(" ", text.replace("−", "-"))
    secondary_only = bool(SECONDARY.search(text)) and not OVERALL.search(text)
    problems = []
    for name, pattern, suffixes in LABELS:
        for m in pattern.finditer(cleaned):
            token = m.group(1)
            fields = [v for path, v in cited.items() if path.endswith(suffixes)
                      and not (secondary_only and "/primary/" in path)]
            if not any(number_matches(token, False, v) for v in fields):
                problems.append(f"{name} = {token}")
    return problems


def _cited(cited: dict[str, object], suffix: str) -> list[float]:
    return [v for p, v in cited.items() if p.endswith(suffix) and isinstance(v, (int, float)) and not isinstance(v, bool)]


def _flag_established(flag: str, cited: dict[str, object]) -> bool:
    """R11 alternative: the cited evidence itself establishes the flag under its saved rule."""
    if flag == "disconnected":
        return any(v > 1 for v in _cited(cited, "components")) or any(v > 0 for v in _cited(cited, "isolated_nodes"))
    if flag == "incomplete_observation":
        return any(v > 0 for v in _cited(cited, "unknown_pairs"))
    if flag == "degree_confound":  # the saved rule: max degree >= DEGREE_CONFOUND_RATIO x max(median, 1)
        return any(hi >= DEGREE_CONFOUND_RATIO * max(md, 1) for hi in _cited(cited, "degree_max") for md in _cited(cited, "degree_median"))
    return False


@dataclass(frozen=True)
class CriticContext:
    evidence: dict[str, object]  # flattened artifact path -> scalar value
    verdict: str | None
    delta_q: float | None
    p_value: float | None
    alpha: float


class CriticDecision(Contract):
    claim: dict
    accepted: bool
    reasons: tuple[NonEmpty, ...] = ()
    flags: tuple[NonEmpty, ...] = ()


def critique(claim: object, ctx: CriticContext) -> CriticDecision:
    reasons: list[str] = []
    flags: list[str] = []
    if not isinstance(claim, dict):
        return CriticDecision(claim={"raw": str(claim)[:200]}, accepted=False, reasons=("R1: claim is not an object",))
    text, level, links = claim.get("text"), claim.get("evidence_level"), claim.get("evidence", [])
    if not isinstance(text, str) or not text.strip() or len(text) > 500:
        reasons.append("R1: text missing or longer than 500 characters")
        text = str(text or "")
    if level not in {e.value for e in EvidenceLevel}:
        reasons.append(f"R1: unknown evidence level {str(level)[:40]!r}")
    if not isinstance(links, list) or not all(isinstance(x, str) for x in links):
        reasons.append("R1: evidence must be a list of artifact paths")
        links = []
    if level != EvidenceLevel.UNSUPPORTED and not links:
        reasons.append("R2: factual claim cites no evidence")
    missing = [x for x in links if x not in ctx.evidence]
    if missing:
        reasons.append(f"R2: cited evidence not found: {missing[:3]}")
    cited = {x: ctx.evidence[x] for x in links if x in ctx.evidence}
    bad = unsupported_numbers(text, list(cited.values()))
    if bad:
        reasons.append(f"R3: numbers not matching cited evidence: {bad[:5]}")
    wrong_meaning = mislabelled_numbers(text, cited)
    if wrong_meaning:
        reasons.append(f"R3: labelled numbers do not match a cited field of that meaning: {wrong_meaning[:5]}")
    if level in {e.value for e in EvidenceLevel} and EvidenceLevel(level) not in ALLOWED_LEVELS:
        reasons.append(f"R4: evidence level '{level}' is not supported by any Sprint 1 tool")
        if level == EvidenceLevel.IDENTIFIED_CAUSAL:
            flags.append("causal_not_identified")
    if CAUSAL.search(text):
        reasons.append("R5: causal language without an estimand or identification argument")
        flags.append("causal_not_identified")
    if STRUCTURE.search(text) and ctx.verdict != "supported":
        reasons.append(f"R6: asserts community structure but the preregistered verdict is '{ctx.verdict}'")
    for match in COMPARATIVE.finditer(text):
        if NEGATION.search(text[: match.start()]):
            continue
        if ctx.delta_q is None or ctx.p_value is None or not (ctx.delta_q > 0 and ctx.p_value <= ctx.alpha):
            reasons.append("R7: says observed exceeds the null, but delta_q/p do not show that")
            break
        sides = [name for name, suffixes in (("an observed value", OBSERVED_SIDE), ("a null-side value", NULL_SIDE),
                                             ("the test conclusion (p-value or verdict)", CONCLUSION))
                 if not any(path.endswith(suffixes) for path in cited)]
        if sides:
            reasons.append(f"R7: comparison with the null does not cite {', '.join(sides)}")
        break
    for match in REGISTERED.finditer(text):
        if not NEGATION.search(text[: match.start()]):
            reasons.append("R9: 'preregistered' is not established by any cited artifact; say 'the saved "
                           "decision-rule verdict' instead")
            break
    if SECONDARY.search(text) and re.search(r"\bverdict\b", text, re.I) and not OVERALL.search(text) and \
            any(path.endswith(("#/verdict", "#/raw_verdict")) for path in cited):
        reasons.append("R10: a secondary/largest-component verdict cites the overall verdict field; the secondary "
                       "analysis has no verdict of its own: say 'the overall verdict' or cite secondary results")
    for flag, pattern in FLAG_NAMES.items():
        for match in re.finditer(pattern, text, re.I):
            if NEGATION.search(text[: match.start()]):
                continue
            if not (any("#/flags/" in path and value == flag for path, value in cited.items())
                    or _flag_established(flag, cited)):
                reasons.append(f"R11: asserts the {flag} flag without citing that flag or the evidence that "
                               "establishes it")
            break
    if NULL_RANGE.search(text) and not all(any(path.endswith(q) for path in cited) for q in ("null/q05", "null/q95")):
        reasons.append("R12: a position relative to the null range needs the cited null q05 and q95")
    if PAIRING.search(text):
        reasons.append("R13: delta Q is a difference (observed - null mean); comparing it with the null mean mixes "
                       "quantities: compare observed Q with the null mean")
    strength = STRENGTH.search(text)
    if strength:
        reasons.append(f"R8: strength wording {strength.group(1)!r} has no preregistered threshold; report the "
                       "numbers (Q, null mean, delta Q, p) instead")
    return CriticDecision(claim=claim, accepted=not reasons, reasons=tuple(reasons), flags=tuple(dict.fromkeys(flags)))


# --- Pre-execution plan validator ---------------------------------------------------------------


class PlanDecision(Contract):
    allowed: bool
    refusal_flag: str | None = None
    reasons: tuple[NonEmpty, ...] = ()
    tool_calls: tuple[dict, ...] = ()


ORDER = {"profile_graph": 0, "community_test": 1, "edge_removal_sensitivity": 2}
# The preregistered protocol (exp-v1.1 §1-§9) answers the question with both analyses; neither is optional.
REQUIRED_TOOLS = {"community_test": {"method": "louvain"}, "edge_removal_sensitivity": {}}


def validate_plan(question: str, request: dict, plan: dict) -> PlanDecision:
    """Refuse causal requests and non-allowlisted methods before anything runs.

    Raises AnswerKeyAccess if the plan reaches for evaluator-only data.
    """
    from blackgrid.agent.inquiry import family, validate_structural
    if family(question, request) != "community":
        allowed, calls, reason = validate_structural(question, request, plan)
        return PlanDecision(allowed=allowed, tool_calls=tuple(calls), reasons=(reason,))
    if CAUSAL.search(question) or str(request.get("claim_type", "")).lower() == "causal":
        return PlanDecision(allowed=False, refusal_flag="causal_not_identified",
                            reasons=("Causal effects are not identified: static observational graph, no estimand, "
                                     "no intervention, no identification argument.",))
    method = str(request.get("method", "auto"))
    if method not in ("auto", "louvain"):
        return PlanDecision(allowed=False, refusal_flag="invalid_method",
                            reasons=(f"Requested method {method[:40]!r} is not allowlisted for the preregistered "
                                     f"experiment.",))
    if plan.get("decision") == "refuse":
        return PlanDecision(allowed=False, refusal_flag=None, reasons=("planner refused the task",))
    calls = plan.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        return PlanDecision(allowed=False, reasons=("plan contains no tool calls",))
    checked: list[dict] = []
    for call in calls[:6]:
        try:
            name, args = parse_request(call)
        except AnswerKeyAccess:
            raise
        except ToolRejected as exc:
            return PlanDecision(allowed=False, refusal_flag="invalid_method", reasons=(str(exc),))
        checked.append({"tool": name, "args": args.model_dump(mode="json")})
        if name not in ORDER:
            return PlanDecision(allowed=False, reasons=("Tool does not belong to the frozen community protocol.",))
    planned = {c["tool"] for c in checked}
    added = [name for name in REQUIRED_TOOLS if name not in planned]
    checked += [{"tool": name, "args": REQUIRED_TOOLS[name]} for name in added]
    checked.sort(key=lambda c: ORDER[c["tool"]])  # enforce prerequisite order
    reasons = tuple(f"added {name}: required by the preregistered protocol but omitted by the planner"
                    for name in added)
    return PlanDecision(allowed=True, reasons=reasons, tool_calls=tuple(checked))
