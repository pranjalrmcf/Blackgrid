"""Question-specific structural plans and exact, evidence-bound claim forms."""
from __future__ import annotations

import re

from blackgrid.tools import ARTIFACT_NAMES, FORECAST_TOOLS, AnswerKeyAccess, ToolRejected, parse_request

STRUCTURAL_TOOLS = {"profile_graph", "node_centrality", "community_partition", "community_bridge", "ranking_sensitivity"}


CAUSAL_Q = re.compile(r"\b(influen\w*|caus\w*|persuad\w*|why)\b")
# Forecast wording (D-080): "next few weeks", "over the coming month", "likely to keep talking", "will start messaging".
FORECAST = re.compile(
    r"\b(forecast\w*|predict\w*|future|"
    r"next(?:\s+\w+){0,2}\s+(?:weeks?|months?|days?|window|period)|"
    r"(?:in|over|during|within)\s+the\s+(?:next|coming)|coming\s+(?:weeks?|months?|days)|"
    r"will\s+(?:\w+\s+){0,2}(?:message|talk|contact|connect|interact|chat|start|keep|continue)\w*|"
    r"likely\s+to\s+(?:\w+\s+){0,2}(?:message|talk|contact|connect|interact|chat|start|keep|continue)\w*|"
    r"keep\s+(?:talking|messaging|chatting|in touch)|start\s+(?:talking|messaging|chatting)|"
    r"(?:new|future)\s+connections?)")
# Bridge wording: "connect otherwise separate groups", "between communities", "cross-group".
BRIDGE = re.compile(
    r"\b(bridg\w*|cross.(?:community|group)|connect\w*(?:\s+\w+){0,3}\s+(?:groups|communities|clusters)|"
    r"between\s+(?:different\s+|separate\s+)?(?:groups|communities|clusters))\b")


def family(question: str, request: dict) -> str:
    selected = request.get("family", "community")
    if selected != "auto":
        return selected
    q = question.lower()
    if CAUSAL_Q.search(q):
        return "clarify"
    if FORECAST.search(q):
        return "forecast"
    if BRIDGE.search(q):
        return "bridge"
    # A degree-preserving null describes the community baseline, not a request
    # to rank nodes by degree. Keep genuine centrality requests distinct.
    centrality_question = re.sub(r"\bdegree[\s\-–—]+preserv\w*\b", "", q)
    if re.search(r"\b(central\w*|contacts|betweenness|shortest paths?|degree)\b", centrality_question):
        return "centrality"
    if re.search(r"\b(communit\w*|cluster\w*|modular\w*)\b", q):
        return "community"
    return "clarify"


def forecast_task(question: str) -> str:
    """Repeat interactions when the question is about pairs that already talked; otherwise new pairs."""
    return "repeat_pair" if re.search(r"\b(again|repeat\w*|already|previous\w*|continue|keep (?:talking|messaging)|"
                                      r"existing)\b", question, re.I) else "new_pair"


def requirements(question: str, request: dict) -> dict[str, dict]:
    kind = family(question, request)
    if kind == "forecast":
        task = forecast_task(question)
        return {"link_prediction": {"task": task}, "prediction_compare": {"task": task, "split": "rolling"}}
    if kind == "centrality":
        required = {"node_centrality": {}}
    elif kind == "bridge":
        required = {"community_partition": {}, "community_bridge": {}}
    else:
        return {}
    if re.search(r"\b(stab\w*|robust\w*|reliable|missing|sensitive|sensitivity)\b", question, re.I):
        required["ranking_sensitivity"] = {}
    return required


def validate_structural(question: str, request: dict, plan: dict) -> tuple[bool, list[dict], str]:
    if family(question, request) == "clarify":
        if CAUSAL_Q.search(question.lower()):
            return False, [], ("This asks about causes, influence or persuasion, which observational message data cannot "
                               "establish. Ask what the network shows, or which known pairs are likely to message next.")
        return False, [], ("I could not match this to a supported analysis. Try asking about communities, people with many "
                           "contacts or central positions, people who connect separate groups, or which known pairs are "
                           "likely to message in the next few weeks.")
    if family(question, request) == "forecast":
        return validate_forecast(question, request, plan)
    if re.search(r"\b(caus\w*|influen\w*|persuad\w*|predict\w*)\b", question, re.I):
        return False, [], "Clarify the structural question; these tools do not identify causal influence or predict future edges."
    if plan.get("decision") == "refuse":
        return False, [], "Planner refused this structural question."
    calls = plan.get("tool_calls")
    if not isinstance(calls, list) or not 1 <= len(calls) <= 6:
        return False, [], "A plan needs one to six registered calls."
    checked, names = [], set()
    allowed_tools = {"profile_graph", "ranking_sensitivity"} | (
        {"node_centrality"} if family(question, request) == "centrality" else {"community_partition", "community_bridge", "node_centrality"})
    for call in calls:
        try:
            name, args = parse_request(call)
        except AnswerKeyAccess:
            raise
        except ToolRejected as exc:
            return False, [], str(exc)
        if name not in allowed_tools or name in names:
            return False, [], "Structural plan contains an incompatible or duplicate tool."
        names.add(name)
        checked.append({"tool": name, "args": args.model_dump(mode="json")})
    # Prerequisites and question obligations belong to the controller, not to model discretion.
    required = requirements(question, request)
    if "community_bridge" in names:
        required = {"community_partition": {}} | required
    if "ranking_sensitivity" in names and not names & {"community_bridge", "node_centrality"}:
        required = required | ({"community_bridge": {}, "community_partition": {}} if family(question, request) == "bridge"
                               else {"node_centrality": {}})
    for name in required:
        if name not in names:
            checked.append({"tool": name, "args": {}})
            names.add(name)
    order = {"profile_graph": 0, "node_centrality": 1, "community_partition": 2,
             "community_bridge": 3, "ranking_sensitivity": 4}
    checked.sort(key=lambda c: order[c["tool"]])
    return True, checked, "Validated descriptive structural plan; numerical settings are fixed."


def validate_forecast(question: str, request: dict, plan: dict) -> tuple[bool, list[dict], str]:
    """Forecast plans: registered forecast tools only; one link_prediction; compare uses the same task."""
    if plan.get("decision") == "refuse":
        return False, [], "Planner refused this forecasting question."
    calls = plan.get("tool_calls")
    if not isinstance(calls, list) or not 1 <= len(calls) <= 6:
        return False, [], "A forecast plan needs one to six registered calls."
    checked: dict[str, dict] = {}
    dropped: list[str] = []
    for call in calls:
        try:
            name, args = parse_request(call)  # unknown tools, bad arguments: refused as before
        except AnswerKeyAccess:
            raise
        except ToolRejected as exc:
            return False, [], str(exc)
        if name not in FORECAST_TOOLS or name in checked:
            # D-081: a registered but inapplicable tool (e.g. ranking_sensitivity for "how reliable") or a duplicate
            # is dropped by the controller and noted, instead of rejecting a sound forecast plan.
            dropped.append(name)
            continue
        checked[name] = args.model_dump(mode="json")
    if not checked:
        return False, [], "The plan contains no forecast tool; forecasts use link_prediction and prediction_compare."
    required = requirements(question, request)
    task = checked.get("link_prediction", required["link_prediction"])["task"]
    checked.setdefault("link_prediction", {"task": task})
    method = checked["link_prediction"].get("method", "selected")
    # The selected (promoted) model is evaluated in the rolling evidence; v1 test/validation tables describe other
    # methods, so the controller fixes the split to match the forecast's method (D-079).
    split = "rolling" if method in ("selected", "logistic_v2") else \
        checked.get("prediction_compare", {}).get("split", "test")
    checked["prediction_compare"] = {"task": task, "split": split}
    order = {"temporal_profile": 0, "link_prediction": 1, "prediction_compare": 2}
    plan_calls = [{"tool": name, "args": checked[name]} for name in sorted(checked, key=order.get)]
    note = (f" Ignored tools that do not apply to forecasts: {', '.join(dict.fromkeys(dropped))}; past reliability "
            "comes from prediction_compare." if dropped else "")
    return True, plan_calls, "Validated forecast plan; cutoff, horizon and candidates are fixed by the system." + note


def safe_outputs(outputs: dict[str, dict]) -> dict[str, dict]:
    """No node rows, IDs or partition membership in external model evidence."""
    return {name: {k: v for k, v in payload.items() if k != "rows"} if name in
            {ARTIFACT_NAMES[t] for t in STRUCTURAL_TOOLS - {"profile_graph"}} else payload
            for name, payload in outputs.items()}


def factual_claims(evidence: dict[str, object]) -> list[dict]:
    """Local exact claim vocabulary; unknown structural prose is unassessed, not auto-approved."""
    claims = []
    for tool, field, wording in (
        ("node_centrality", "max_degree", "The maximum observed degree is"),
        ("node_centrality", "max_betweenness", "The maximum normalized betweenness estimate is"),
        ("community_partition", "communities", "The descriptive partition contains this many communities:"),
        ("community_bridge", "max_cross_degree", "The maximum cross-community degree is"),
        ("ranking_sensitivity", "mean_top_jaccard", "Mean tie-inclusive top-set Jaccard under assumed uniform edge removal is"),
    ):
        path = f"{ARTIFACT_NAMES[tool]}#/summary/{field}"
        if path in evidence:
            claims.append({"text": f"{wording} {evidence[path]}.", "evidence_level": "descriptive", "evidence": [path]})
    return claims
