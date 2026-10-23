"""Public tool catalog and aggregate-only results for the existing workflows."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from blackgrid.agent.tools import ARTIFACT_NAMES

CATALOG = {
    "profile_graph": ("community", "Graph size, components and degree summary"),
    "community_test": ("community", "Community structure versus a degree-preserving null model"),
    "edge_removal_sensitivity": ("community", "Community verdict sensitivity to edge removal"),
    "node_centrality": ("centrality", "Degree and betweenness centrality"),
    "community_partition": ("bridge", "Descriptive community partition"),
    "community_bridge": ("bridge", "Connections between observed communities"),
    "ranking_sensitivity": ("centrality", "Ranking stability under assumed edge removal"),
    "behavior_features": ("behavior", "Directed-event activity profiles"),
    "behavior_clustering": ("behavior", "Descriptive clustering of activity profiles"),
    "behavior_similarity": ("behavior", "Similarity between observed activity profiles"),
    "behavior_anomalies": ("behavior", "Unusual activity candidates and count-only baseline"),
    "temporal_profile": ("forecast", "Observed history at the fixed forecast cutoff"),
    "link_prediction": ("forecast", "Future messaging-pair rankings over the fixed horizon"),
    "prediction_compare": ("forecast", "Historical ranking evaluation and confirmation aggregates"),
    "reliability_audit": ("research", "Saved synthetic calibration and bootstrap evidence"),
    "belief_update": ("research", "Saved synthetic Bayesian beliefs"),
    "experiment_decision": ("research", "Saved synthetic experiment-or-stop decision"),
    "causal_identification_check": ("research", "Saved synthetic causal assumptions and real-data non-identification"),
}

SCOPES = {
    "community": ("descriptive", "configured observed graph only"),
    "centrality": ("descriptive", "configured observed graph; centrality is not causal influence"),
    "bridge": ("descriptive", "configured observed graph; partition-dependent descriptive bridges"),
    "behavior": ("descriptive", "recorded directed-event window; unusual profiles are not verified anomalies"),
    "forecast": ("predictive", "full validated observed history; fixed horizon and known-node ranking scores, not calibrated probabilities"),
    "research": ("descriptive", "pinned saved synthetic demonstration only; not evidence about the selected real graph"),
    "clarify": ("unsupported", "question requires clarification or an unsupported inference"),
}

# Known aggregate fields only. New/private fields in an artifact cannot silently
# become API output. Local node/pair rows and fitted coefficients never appear.
FIELDS = {
    "profile_graph": "nodes edges isolated_nodes components largest_component_nodes largest_component_edges density degree_min degree_median degree_mean degree_max transitivity",
    "node_centrality": "metric normalization approximate sample_sources max_degree max_betweenness",
    "community_partition": "method resolution restarts communities interpretation",
    "community_bridge": "metric max_cross_degree interpretation",
    "ranking_sensitivity": "metric mechanism removal_fraction replicates mean_top_jaccard mean_spearman degree_mean_top_jaccard degree_mean_spearman betweenness_mean_top_jaccard betweenness_mean_spearman",
    "behavior_features": "nodes nonzero_profiles zero_profiles events excluded_self_events",
    "behavior_clustering": "nodes nonzero_profiles zero_profiles events excluded_self_events clusters silhouette inertia",
    "behavior_similarity": "nodes nonzero_profiles zero_profiles neighbor_rows max_similarity",
    "behavior_anomalies": "nodes nonzero_profiles zero_profiles candidates max_deviation count_baseline_candidates candidate_overlap",
    "temporal_profile": "cutoff horizon_s history_events history_nodes history_pairs first_event",
    "link_prediction": "task method cutoff horizon_s scope history_nodes history_pairs horizon_days candidates candidate_policy scores top_score_ties",
    "prediction_compare": "task split windows evidence requested_split note mean_ap_difference",
    "reliability_audit": "graphs probability_display bootstrap_confidence_lower bootstrap_confidence_upper scope",
    "belief_update": "target",
    "experiment_decision": "abstention real_forecast_voi",
    "causal_identification_check": "",
    "edge_removal_sensitivity": "mechanism removal_fraction replicates null_replicates_per_run agreement",
    "community_test": "verdict raw_verdict",
}


def read_artifact(run: Path, name: str) -> dict | None:
    path = run / name
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024**2:
        raise ValueError("unsafe analysis artifact")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("invalid analysis artifact")
    return value


def aggregate(tool: str, payload: dict) -> dict:
    source = payload.get("summary", payload)
    result = {key: source[key] for key in FIELDS[tool].split() if key in source
              and (source[key] is None or type(source[key]) in (str, int, float, bool))}
    if tool == "belief_update":
        result["methods"] = {name: {k: v for k, v in payload.get("methods", {}).get(name, {}).items()
            if k in ("mean", "alpha", "beta", "credible_lower", "credible_upper") and type(v) in (int, float)}
            for name in ("A", "B")}
    if tool == "experiment_decision":
        decision = payload.get("decision") or {}
        result["action"] = decision.get("action") if decision.get("action") in ("A", "B", "stop") else None
    if tool == "causal_identification_check":
        result.update(synthetic_verdict=payload.get("synthetic", {}).get("verdict"),
                      real_verdict=payload.get("real", {}).get("verdict"))
    return result


def expanded_results(run: Path, investigation: dict) -> dict:
    from blackgrid.agent.inquiry import factual_claims, safe_outputs
    from blackgrid.agent.roles import flatten
    from blackgrid.agent.research import workflow_claims
    from blackgrid.workflow.engine import forecast_suggestions
    family = investigation.get("family", "community")
    if family not in SCOPES:
        raise ValueError("unknown result family")
    outputs, analyses = {}, {}
    for tool in CATALOG:
        payload = read_artifact(run, ARTIFACT_NAMES[tool])
        if payload is not None:
            outputs[ARTIFACT_NAMES[tool]] = payload
            analyses[tool] = {"artifact": ARTIFACT_NAMES[tool], "analysis": CATALOG[tool][1],
                              "summary": aggregate(tool, payload)}
    # Reconstruct the existing closed claim vocabulary; never publish arbitrary
    # planner/writer prose, even in tool_only mode or if future fields are added.
    allowed = (forecast_suggestions(SimpleNamespace(outputs=outputs)) if family == "forecast" else
               workflow_claims(flatten(outputs)) if family == "research" else
               factual_claims(flatten(safe_outputs(outputs)))) if family != "community" else []
    reported = investigation.get("reported_claims", [])
    conclusions = [{"text": c["text"], "evidence_level": c["evidence_level"], "evidence": c["evidence"]}
                   for c in allowed if any(r.get("text") == c["text"] and r.get("evidence") == c["evidence"]
                                          for r in reported)]
    claim_type, scope = SCOPES[family]
    result = {"family": family, "claim_type": claim_type, "scope": scope,
            "analyses": analyses, "conclusions": conclusions,
            "missing_analyses": [t for t in investigation.get("missing_analyses", []) if t in CATALOG]}
    if family == "research":
        source = read_artifact(run, "run_source.json") or {}
        profile = source.get("input_ref", {}).get("research_evidence", {}).get("verification_profile")
        if profile not in (None, "api-beliefs-portability-v1"):
            raise ValueError("unknown research verification profile")
        result["research_verification_profile"] = profile or "exact"
    return result
