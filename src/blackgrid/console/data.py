"""View payloads for the console, built only from saved run artifacts.

The same payloads feed the live console (JSON API) and the static snapshots (embedded JSON), so
both modes always show the same thing. Deliberately excluded: LLM prompts and raw responses
(`llm_trace.jsonl`, `ops/`), configs' secrets (none exist), node identifiers, and anything from
answer keys. Untrusted text (LLM claims, questions) is passed as data and rendered with
`textContent` in the browser, never as HTML.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RUN_FILES = {
    "manifest": "manifest.json", "investigation": "investigation.json", "experiment": "experiment_report.json",
    "sensitivity": "sensitivity.json", "record": "graph_record.json", "profile": "graph_profile.json",
    "layout": "layout.json", "budget": "budget.json", "report": "report.json", "workflow": "workflow_status.json",
    "window": "window_selection.json",
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
    return {
        "id": path.relative_to(runs_dir.resolve()).as_posix(), "kind": "run",
        "case": inv.get("case_id") or record.get("graph_id"),
        "status": manifest.get("status") or ws.get("status") or inv.get("status") or "unknown",
        "verdict": inv.get("verdict"), "stage": ws.get("stage"), "reason": ws.get("reason") or inv.get("failure_reason"),
        "mode": (inv.get("cost") or {}).get("mode"), "condition": inv.get("condition"),
        "pause": ws.get("pause"), "updated": ws.get("updated_utc"),
        "usd": (inv.get("cost") or {}).get("actual_usd"), "llm_calls": (inv.get("cost") or {}).get("llm_calls"),
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
            elif is_run(path):
                items.append(run_summary(runs_dir, path))
    return {"runs": items}


def run_payload(runs_dir: Path, path: Path) -> dict:
    path = path.resolve()
    payload = {key: _load(path / name) for key, name in RUN_FILES.items()}
    payload["id"] = path.relative_to(runs_dir.resolve()).as_posix()
    payload["summary"] = run_summary(runs_dir, path)
    return payload


def pilot_payload(runs_dir: Path, path: Path) -> dict:
    data = _load(path / "pilot.json") or {}
    rows = []
    for row in data.get("rows", []):
        rows.append(row | {"run_id": f"{path.name}/{row.get('run_dir')}"})
    return {"id": path.name, "label": data.get("label"), "evaluator": data.get("evaluator"),
            "benchmark": data.get("benchmark"), "created_utc": data.get("created_utc"),
            "summary": data.get("summary"), "rows": rows}
