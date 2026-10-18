"""Question-specific structural plans and exact, evidence-bound claim forms."""
from __future__ import annotations

import re

from blackgrid.tools import ARTIFACT_NAMES, AnswerKeyAccess, ToolRejected, parse_request

STRUCTURAL_TOOLS = {"profile_graph", "node_centrality", "community_partition", "community_bridge", "ranking_sensitivity"}


def family(question: str, request: dict) -> str:
    selected = request.get("family", "community")
    if selected != "auto":
        return selected
    q = question.lower()
    if re.search(r"\b(influen\w*|caus\w*|predict\w*|future|persuad\w*)\b", q):
        return "clarify"
    if re.search(r"\b(bridg\w*|cross.community|connect\w* (?:different |the )?(?:groups|communities))\b", q):
        return "bridge"
    # A degree-preserving null describes the community baseline, not a request
    # to rank nodes by degree. Keep genuine centrality requests distinct.
    centrality_question = re.sub(r"\bdegree[\s\-–—]+preserv\w*\b", "", q)
    if re.search(r"\b(central\w*|contacts|betweenness|shortest paths?|degree)\b", centrality_question):
        return "centrality"
    if re.search(r"\b(communit\w*|cluster\w*|modularity)\b", q):
        return "community"
    return "clarify"


def requirements(question: str, request: dict) -> dict[str, dict]:
    kind = family(question, request)
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
        return False, [], "Please specify community evidence, structural centrality or cross-community connections; influence and prediction are not supported."
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
