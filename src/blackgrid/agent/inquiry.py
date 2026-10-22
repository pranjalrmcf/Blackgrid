"""Question-specific structural plans and exact, evidence-bound claim forms."""
from __future__ import annotations

import re

from blackgrid.agent.tools import ARTIFACT_NAMES, FORECAST_TOOLS, RESEARCH_TOOLS, AnswerKeyAccess, ToolRejected, parse_request
from blackgrid.analysis.behavior import TOOLS as BEHAVIOR_TOOLS, public_output

STRUCTURAL_TOOLS = {"profile_graph", "node_centrality", "community_partition", "community_bridge", "ranking_sensitivity"}
ANALYSIS_FAMILIES = frozenset({"community", "centrality", "bridge", "forecast", "research", "behavior", "clarify"})
BEHAVIOR = re.compile(r"behavio\w*\s+cluster|similarity|similar\s+(?:users?|nodes?|profiles?|behavio\w*|activity)|anomal\w*|unusual\s+(?:activity|behavio\w*|profiles?)", re.I)


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
RESEARCH = re.compile(r"\b(sprint\s*7|uncertainty|calibrat\w*|credible|confidence intervals?|belief\w*|posterior\w*|"
                      r"next experiment|test next|experiment.{0,25}worth|worth.{0,25}experiment|"
                      r"trust.{0,20}result|causal identif\w*|causal assumptions?)\b")


def unsupported_scope(question: str) -> str | None:
    """Reject unavailable targets instead of substituting saved synthetic evidence."""
    q = question.lower()
    criminal_proof = re.search(r"\b(prov\w*|confirm\w*|verif\w*|identify|determin\w*|establish\w*)\b.{0,100}\b(fraud\w*|scamm?\w*|malicious|criminal\w*)\b", q)
    if criminal_proof and not re.search(r"\bwithout(?:\s+\w+){0,3}\s+$", q[:criminal_proof.start()]):
        return ("Behavioral outlier flags cannot prove fraud, scamming or malicious intent. "
                "Observed messages support descriptive unusual-profile candidates only; independent verified labels are unavailable.")
    if (re.search(r"\b(look|read|use|peek|access)\b.{0,100}\b(held[ -]out|answer[ -]keys?|"
                  r"future (?:messages|events|labels)|next (?:week|month)(?:['’]s)? (?:actual )?messages)", q)):
        return "Future messages and held-out answers cannot be accessed to improve a forecast. The recorded cutoff and information boundary remain fixed."
    if re.search(r"\b(try|search|test|keep trying)\b.{0,80}\bwindows?\b.{0,100}\b(only|significant|significance|0\.05)\b", q):
        return "Selecting time windows to obtain significance and hiding other attempts is not supported. Window selection and the statistical protocol remain frozen."
    causal_review = re.search(r"identif\w*|assumptions?|causal (?:study|review|example)", q)
    saved_causal = causal_review and (re.search(r"\b(saved|stored|synthetic|sprint\s*7)\b", q)
                    or not re.search(r"collegemsg|real[ -](?:world|data)|(?:this|selected) (?:graph|network)", q))
    intervention = (re.search(r"\b(ban\w*|remov\w*|exclud\w*)\b", q)
                    and re.search(r"\b(student|user|person|people|node)\w*\b", q)
                    and re.search(r"\b(fewer|reduc\w*|behavio\w*|absence)\b", q))
    if not saved_causal and (re.search(r"\b(caus\w*|influen\w*|persuad\w*)\b", q) or intervention):
        return ("Observed messages and graph deletion cannot identify a real behavioral causal effect or influence. "
                "A defined intervention, outcome, estimand and defensible identification assumptions are required.")
    probability = re.search(r"\b(probabilit\w*|chances?|odds)\b", q)
    real_target = re.search(r"\b(collegemsg|real[ -](?:world|data|forecast\w*)|(?:this|selected|observed) (?:network|graph))\b", q)
    pair_target = re.search(r"\b(pairs?|message\w*|messag\w*|tomorrow)\b", q)
    if probability and pair_target:
        return ("An exact calibrated probability for an individual messaging pair is unavailable. The system ranks "
                "known-node pairs with uncalibrated scores over a fixed horizon; it cannot select an arbitrary pair "
                "or change that horizon to tomorrow. Historical ranking evaluation is available as a separate question.")
    if real_target and re.search(r"\b(synthetic|posterior\w*|belief\w*|calibrat\w*)\b", q):
        return ("Saved synthetic posteriors describe success rates under a synthetic model. They cannot give the "
                "probability that CollegeMsg has real communities or calibrate probabilities in the selected real "
                "network. A community-versus-null test or historical forecast ranking evaluation answers a different question.")
    return None


def resolve_plan_family(question: str, request: dict, plan: dict) -> str:
    """Semantic choice from a real plan; bounded family/tool validation stays in the controller."""
    if unsupported_scope(question):
        return "clarify"
    if request.get("family", "community") != "auto":
        return family(question, request)
    declared = plan.get("family")
    if declared is not None:
        if not isinstance(declared, str) or declared not in ANALYSIS_FAMILIES:
            raise ToolRejected("Planner family must be one of the registered analysis families.")
    if plan.get("decision") == "refuse":
        return "clarify"
    if declared is not None:
        return checked_family(question, declared)
    # Compatibility with real replies that omit family: their registered tools also encode intent.
    calls = plan.get("tool_calls")
    names = {c.get("tool") for c in calls if isinstance(c, dict) and isinstance(c.get("tool"), str)} if isinstance(calls, list) else set()
    groups = set()
    if names & {"community_test", "edge_removal_sensitivity"}: groups.add("community")
    if names & set(FORECAST_TOOLS): groups.add("forecast")
    if names & set(RESEARCH_TOOLS): groups.add("research")
    if names & set(BEHAVIOR_TOOLS): groups.add("behavior")
    if names & {"community_partition", "community_bridge"}: groups.add("bridge")
    if "node_centrality" in names and "bridge" not in groups: groups.add("centrality")
    if len(groups) == 1:
        return checked_family(question, groups.pop())
    if len(groups) > 1:
        raise ToolRejected("Planner mixed incompatible analysis families; no tools were executed.")
    return family(question, request)


def checked_family(question: str, selected: str) -> str:
    """Reject clear target substitution while retaining semantic routing for ambiguous wording."""
    q=question.lower()
    saved=bool(re.search(r'\b(saved|stored|synthetic|posterior)\b',q))
    if BEHAVIOR.search(q) and selected != "behavior" and not FORECAST.search(q):
        raise ToolRejected("Behavioral analysis requires the behavior family and directed-event tools.")
    if not saved and not CAUSAL_Q.search(q) and re.search(r'\bpairs?\b',q) and FORECAST.search(q):
        if selected!='forecast':
            raise ToolRejected('A messaging-pair forecast cannot be replaced by structural tools.')
    if re.search(r'cross[ -](?:community|group)',q) and re.search(r'\brank\w*\b',q) and selected=='centrality':
        raise ToolRejected('Cross-community rankings require the bridge family, not ordinary centrality.')
    return selected


def planner_refusal(plan: dict, fallback: str) -> str:
    """Keep the explanation visible without promoting model text to a checked finding."""
    reason = plan.get("reason")
    return fallback + (" Planner explanation (unverified): " + reason.strip()[:500]
                       if isinstance(reason, str) and reason.strip() else "")


def family(question: str, request: dict) -> str:
    if unsupported_scope(question):
        return "clarify"
    selected = request.get("family", "community")
    if selected != "auto":
        return selected
    q = question.lower()
    if BEHAVIOR.search(q) and not FORECAST.search(q) and not CAUSAL_Q.search(q):
        return "behavior"
    if FORECAST.search(q) and not re.search(r"\b(synthetic|saved|sprint\s*7)\b", q) and not CAUSAL_Q.search(q):
        return "forecast"
    if RESEARCH.search(q):
        return "research"
    if CAUSAL_Q.search(q):
        return "clarify"
    if FORECAST.search(q):
        return "forecast"
    if BRIDGE.search(q):
        return "bridge"
    if (re.search(r"\b(communit\w*|cluster\w*|modular\w*)\b", q)
            and re.search(r"\b(expected|explain\w*|baseline|null|random\w*)\b", q)
            and not re.search(r"\b(centrality|betweenness|shortest paths?|rank\w*)\b", q)):
        return "community"
    # A degree-preserving null describes the community baseline, not a request
    # to rank nodes by degree. Keep genuine centrality requests distinct.
    centrality_question = re.sub(r"\bdegree[\s\-–—]+preserv\w*\b", "", q)
    if re.search(r"\b(communit\w*|cluster\w*|modular\w*)\b", q):
        # A community null-model question may name the degree sequence/distribution.
        # Those phrases are baseline context; explicit node-ranking cues still take precedence.
        centrality_question = re.sub(r"\bdegree[\s\-–—]+(?:sequence|distribution)\b", "", centrality_question)
    if re.search(r"\b(central\w*|contacts|betweenness|shortest paths?|degree)\b", centrality_question):
        return "centrality"
    if re.search(r"\b(communit\w*|cluster\w*|modular\w*)\b", q):
        return "community"
    return "clarify"


def forecast_task(question: str) -> str:
    """Repeat interactions when the question is about pairs that already talked; otherwise new pairs."""
    if re.search(r"\b(never|first[ -]time|unconnected|no (?:prior|previous))\b", question, re.I):
        return "new_pair"
    return "repeat_pair" if re.search(r"\b(again|repeat\w*|already|previous\w*|prior|resum\w*|continue|keep (?:talking|messaging)|"
                                      r"existing)\b", question, re.I) else "new_pair"


def requirements(question: str, request: dict) -> dict[str, dict]:
    kind = family(question, request)
    if kind == "behavior":
        q = question.lower()
        names = ["behavior_features"]
        if re.search(r"cluster", q): names.append("behavior_clustering")
        if re.search(r"similar", q): names.append("behavior_similarity")
        if re.search(r"anomal|unusual", q) and not excludes_anomaly_analysis(q):
            names.append("behavior_anomalies")
        grouped = re.search(r"\b(?:per|each|every|by|within|across|break\s+down)\b(?:\s+[\w-]+){0,4}\s+(?:clusters?|groups?|segments?)\b", q)
        if grouped and not excludes_anomaly_analysis(q) and re.search(r"\b(?:outlier\w*|anomal\w*|unusual|flags?|flagged|candidates?)\b", q):
            names += ["behavior_clustering", "behavior_anomalies"]
        # For implicit wording the validated semantic plan selects the analysis.
        # Missing keyword obligations must not expand a narrow plan to every method.
        return {name: {} for name in names}
    if kind == "research":
        q = question.lower()
        names = []
        if re.search(r"uncertainty|calibrat|confidence interval|trust|reliability", q):
            names += ["reliability_audit"]
        if re.search(r"belief|posterior|credible|next experiment|test next|worth", q):
            names += ["belief_update"]
        if re.search(r"next experiment|test next|worth|decision", q):
            names += ["experiment_decision"]
        if re.search(r"causal|identif|assumption", q):
            names += ["causal_identification_check"]
        return {name: {} for name in (names or RESEARCH_TOOLS)}
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


def excludes_anomaly_analysis(question: str) -> bool:
    """Respect an explicit analysis exclusion, not just the presence of a method keyword."""
    return bool(re.search(r"\b(?:without|leaving\s+out|excluding|omit(?:ting)?)\s+(?:an?\s+)?(?:anomal\w*|outlier\w*)\b", question, re.I))


def validate_structural(question: str, request: dict, plan: dict) -> tuple[bool, list[dict], str]:
    scope_problem = unsupported_scope(question)
    if scope_problem:
        return False, [], scope_problem
    if family(question, request) == "behavior":
        if plan.get("decision") == "refuse":
            return False, [], planner_refusal(plan, "Planner refused this behavioral question.")
        calls = plan.get("tool_calls")
        if not isinstance(calls, list) or not 1 <= len(calls) <= 4:
            return False, [], "A behavioral plan needs one to four registered calls."
        names = set()
        for call in calls:
            try:
                name, _ = parse_request(call)
            except ToolRejected as exc:
                return False, [], str(exc)
            if name not in BEHAVIOR_TOOLS or name in names:
                return False, [], "Incompatible or duplicate behavioral tool."
            names.add(name)
        names.update(requirements(question, request))
        if excludes_anomaly_analysis(question):
            names.discard("behavior_anomalies")
        names.add("behavior_features")
        if names == {"behavior_features"}:
            return False, [], "A behavioral investigation requires at least one registered analysis, not features alone."
        return True, [{"tool": name, "args": {}} for name in BEHAVIOR_TOOLS if name in names], "Fixed descriptive behavioral methods; no causal or probability claims."
    if family(question, request) == "research":
        if plan.get("decision") == "refuse":
            return False, [], planner_refusal(plan, "Planner refused the research question.")
        calls = plan.get("tool_calls")
        if not isinstance(calls, list) or not 1 <= len(calls) <= 6:
            return False, [], "A research plan requires one to six registered calls."
        checked = {}
        for call in calls:
            try:
                name, args = parse_request(call)
            except ToolRejected as exc:
                return False, [], str(exc)
            if name not in RESEARCH_TOOLS:
                return False, [], "Research plans may use only the registered research evidence tools."
            checked[name] = args.model_dump(mode="json")
        for name in requirements(question, request):
            checked.setdefault(name, {})
        return True, [{"tool": name, "args": checked[name]} for name in RESEARCH_TOOLS if name in checked], \
            "Inspect frozen synthetic evidence only; no real probabilities, causal effects or new experiment execution."
    if family(question, request) == "clarify":
        if CAUSAL_Q.search(question.lower()):
            return False, [], ("This asks about causes, influence or persuasion, which observational message data cannot "
                               "establish. Ask what the network shows, or which known pairs are likely to message next.")
        if plan.get("decision") == "refuse":
            return False, [], planner_refusal(plan, "The planner could not support this request with the available evidence.")
        return False, [], ("I could not match this to a supported analysis. Try asking about communities, people with many "
                           "contacts or central positions, people who connect separate groups, or which known pairs are "
                           "likely to message in the next few weeks.")
    if family(question, request) == "forecast":
        return validate_forecast(question, request, plan)
    if re.search(r"\b(caus\w*|influen\w*|persuad\w*|predict\w*)\b", question, re.I):
        return False, [], "Clarify the structural question; these tools do not identify causal influence or predict future edges."
    if plan.get("decision") == "refuse":
        return False, [], planner_refusal(plan, "Planner refused this structural question.")
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
        return False, [], planner_refusal(plan, "Planner refused this forecasting question.")
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
    return {name: public_output(payload) if name in {ARTIFACT_NAMES[t] for t in BEHAVIOR_TOOLS} else
            {k: v for k, v in payload.items() if k != "rows"} if name in
            {ARTIFACT_NAMES[t] for t in STRUCTURAL_TOOLS - {"profile_graph"}} else payload
            for name, payload in outputs.items()}


def factual_claims(evidence: dict[str, object]) -> list[dict]:
    """Local exact claim vocabulary; unknown structural prose is unassessed, not auto-approved."""
    claims = []
    for i in range(3):
        base = f"behavior_anomalies.json#/summary/cluster_comparison/{i}/"
        fields = ("cluster", "size", "candidates", "count_baseline_candidates")
        if all(base + f in evidence for f in fields):
            k, size, candidates, baseline = (evidence[base + f] for f in fields)
            claims.append({"text": f"Behavioral cluster {k} contains {size} profiles, with {candidates} unusual-profile candidates and {baseline} count-only baseline candidates; these are descriptive flags, not confirmed anomalies.",
                           "evidence_level": "descriptive", "evidence": [base + f for f in fields]})
    for tool, field, wording in (
        ("behavior_features", "nonzero_profiles", "The observed window has this many nonzero behavioral profiles:"),
        ("behavior_clustering", "clusters", "Fixed k=3 KMeans produced this many descriptive behavioral clusters:"),
        ("behavior_clustering", "silhouette", "Within-window standardized behavioral silhouette is"),
        ("behavior_similarity", "neighbor_rows", "Local cosine search returned this many non-self neighbor rows:"),
        ("behavior_anomalies", "candidates", "The fixed robust-deviation rule flagged this many unusual-profile candidates, not confirmed anomalies:"),
        ("behavior_anomalies", "count_baseline_candidates", "The count-only deviation baseline flagged this many candidates:"),
    ):
        path = f"{ARTIFACT_NAMES[tool]}#/summary/{field}"
        if path in evidence and evidence[path] is not None:
            claims.append({"text": f"{wording} {evidence[path]}.", "evidence_level": "descriptive", "evidence": [path]})
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
    for metric in ("degree", "betweenness"):
        path = f"ranking_sensitivity.json#/summary/{metric}_mean_top_jaccard"
        if path in evidence:
            claims.append({"text": f"Mean tie-inclusive top-set Jaccard for {metric} under assumed uniform edge removal is {evidence[path]}.",
                           "evidence_level": "descriptive", "evidence": [path]})
    return claims
