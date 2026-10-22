"""View payloads for the console, built only from saved run artifacts.

The same payloads feed the live console (JSON API) and the static snapshots (embedded JSON), so
both modes always show the same thing. Deliberately excluded: LLM prompts and raw responses
(`llm_trace.jsonl`, `ops/`), configs' secrets (none exist), and anything from
answer keys. Local ranking tables may contain node references; these are not model evidence.
Untrusted text (LLM claims, questions) is passed as data and rendered with
`textContent` in the browser, never as HTML.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RUN_FILES = {
    **{name: f"{name}.json" for name in ("behavior_features", "behavior_clustering", "behavior_similarity", "behavior_anomalies")},
    "manifest": "manifest.json", "investigation": "investigation.json", "experiment": "experiment_report.json",
    "sensitivity": "sensitivity.json", "record": "graph_record.json", "profile": "graph_profile.json",
    "layout": "layout.json", "budget": "budget.json", "report": "report.json", "workflow": "workflow_status.json",
    "window": "window_selection.json",
    "centrality": "node_centrality.json", "partition": "community_partition.json",
    "bridges": "community_bridge.json", "ranking_sensitivity": "ranking_sensitivity.json",
    "forecast_profile": "temporal_profile.json", "link_prediction": "link_prediction.json",
    "prediction_compare": "prediction_compare.json", "local_ranking": "local_ranking.json",
    "reliability": "reliability.json", "beliefs": "beliefs.json", "decisions": "decisions.json",
    "causal": "causal.json", "sprint7_manifest": "sprint7_manifest.json",
    "research_contract": "research_contract.json", "reliability_audit": "reliability_audit.json",
    "belief_update": "belief_update.json", "experiment_decision": "experiment_decision.json",
    "causal_identification_check": "causal_identification_check.json",
}
SAFE_ID = re.compile(r"^[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)?$")


def _load(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, ValueError):
        return None


def resolve(runs_dir: Path, run_id: str) -> Path | None:
    """Map a run ID ('RUN' or 'pilot-X/RUN') to its folder, refusing anything outside runs_dir."""
    if not SAFE_ID.match(run_id) or ".." in run_id:
        return None
    path = (runs_dir / run_id).resolve()
    root = runs_dir.resolve()
    if root not in path.parents or not path.is_dir():
        return None
    return path


def is_run(path: Path) -> bool:
    return (path / "workflow_status.json").is_file() or (path / "investigation.json").is_file()


def run_summary(runs_dir: Path, path: Path) -> dict:
    path = path.resolve()  # callers may pass relative folders
    inv = _load(path / "investigation.json") or {}
    ws = _load(path / "workflow_status.json") or {}
    manifest = _load(path / "manifest.json") or {}
    record = _load(path / "graph_record.json") or {}
    config = _load(path / "config.json") or {}
    return {
        "id": path.relative_to(runs_dir.resolve()).as_posix(), "kind": "run",
        "case": inv.get("case_id") or record.get("graph_id"),
        "status": manifest.get("status") or ws.get("status") or inv.get("status") or "unknown",
        "verdict": inv.get("verdict"), "stage": ws.get("stage"), "reason": ws.get("reason") or inv.get("failure_reason"),
        "mode": (inv.get("cost") or {}).get("mode"), "condition": inv.get("condition"),
        "pause": ws.get("pause"), "updated": ws.get("updated_utc"),
        "usd": (inv.get("cost") or {}).get("actual_usd"), "llm_calls": (inv.get("cost") or {}).get("llm_calls"),
        "question": config.get("question"), "family": inv.get("family", "community"),
    }


def index_payload(runs_dir: Path) -> dict:
    root = runs_dir.resolve()
    items = []
    if root.is_dir():
        # Newest first by the timestamp in the folder name (pilot folders are "pilot-<timestamp>").
        for path in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.removeprefix("pilot-"),
                           reverse=True):
            if (path / "pilot.json").is_file():
                data = _load(path / "pilot.json") or {}
                items.append({"id": path.name, "kind": "pilot", "case": "8 dev cases", "status": "completed",
                              "verdict": None, "mode": data.get("mode"), "updated": data.get("created_utc"),
                              "summary": data.get("summary")})
            elif (path / "forecast.json").is_file():
                items.append(forecast_summary(runs_dir, path))
            elif is_run(path):
                items.append(run_summary(runs_dir, path))
    items.sort(key=lambda item: (item.get("updated") or "", item.get("id", "")), reverse=True)
    return {"runs": items}


def run_payload(runs_dir: Path, path: Path) -> dict:
    path = path.resolve()
    payload = {key: _load(path / name) for key, name in RUN_FILES.items()}
    # Local inspection only. Bound browser payload size, but preserve all rows in local artifacts.
    for key in ("centrality", "partition", "bridges"):
        if payload[key]:
            rows = payload[key].get("rows", [])
            metric = "bridge_rank" if key == "bridges" else "betweenness_rank"
            payload[key] = payload[key] | {"rows": sorted(rows, key=lambda r: (r.get(metric, 1), r["node"]))[:500],
                                           "total_rows": len(rows), "display_limit": 500}
    payload["id"] = path.relative_to(runs_dir.resolve()).as_posix()
    payload["summary"] = run_summary(runs_dir, path)
    return payload


TASK_QUESTION = {"new_pair": "Which unconnected pairs are most likely to message next?",
                 "repeat_pair": "Which past pairs are most likely to message again?"}


def forecast_summary(runs_dir: Path, path: Path) -> dict:
    data = _load(path / "forecast.json") or {}
    pred = data.get("prediction") or {}
    return {"id": path.resolve().relative_to(runs_dir.resolve()).as_posix(), "kind": "forecast",
            "case": pred.get("task"), "status": "completed", "verdict": None, "family": "forecast",
            "question": TASK_QUESTION.get(pred.get("task"), "Forecast connections"), "mode": "mock",
            "usd": data.get("usd", 0.0), "updated": data.get("created_utc"), "reason": pred.get("method")}


def forecast_payload(runs_dir: Path, path: Path) -> dict:
    """Local console only: includes the local top-ranked pairs (never exported or sent to a model)."""
    path = path.resolve()
    data = _load(path / "forecast.json") or {}
    ranking = _load(path / "local_ranking.json") or []
    return {"id": path.relative_to(runs_dir.resolve()).as_posix(), "forecast": data, "ranking": ranking[:100],
            "summary": forecast_summary(runs_dir, path)}


def pilot_payload(runs_dir: Path, path: Path) -> dict:
    data = _load(path / "pilot.json") or {}
    rows = []
    for row in data.get("rows", []):
        rows.append(row | {"run_id": f"{path.name}/{row.get('run_dir')}"})
    return {"id": path.name, "label": data.get("label"), "evaluator": data.get("evaluator"),
            "benchmark": data.get("benchmark"), "created_utc": data.get("created_utc"),
            "summary": data.get("summary"), "rows": rows}
