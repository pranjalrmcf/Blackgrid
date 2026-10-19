"""Persistent, opt-in live-console allowance. Historical spend is never reset."""
from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path

from blackgrid.contracts import RunConfig
from blackgrid.workflow.api import open_services

MODEL = "deepseek/deepseek-v4-flash-0731"
CAP_USD = .50


def project_spend(runs_dir: Path) -> float:
    services = open_services(runs_dir)
    try:
        return services.store.spend_elsewhere("__allowance_preflight__")[0]
    finally:
        services.close()


def ensure_allowance(runs_dir: Path, project_ceiling: float | None = None) -> Path:
    """Called only by an explicitly authorized CLI entry point, never a browser request."""
    if project_ceiling is not None and (isinstance(project_ceiling, bool) or
            not math.isfinite(project_ceiling) or project_ceiling <= 0):
        raise ValueError('project ceiling must be a positive finite USD amount')
    path = runs_dir.resolve() / ('console-project-allowance.json' if project_ceiling is not None else 'sprint5-live-allowance.json')
    if path.exists():
        existing = read_allowance(path, runs_dir)
        if project_ceiling is not None and existing['ceiling_project_usd'] != project_ceiling:
            raise ValueError('retained project ceiling differs; existing authorization was not changed')
        return path
    baseline = project_spend(runs_dir)
    payload = {"version": "live-allowance-v1", "model": MODEL, "cap_usd": CAP_USD,
               "baseline_project_usd": baseline, "ceiling_project_usd": baseline + CAP_USD,
               "runs_dir": str(runs_dir.resolve()), "created_utc": datetime.now(UTC).isoformat(),
               "authorization": "User requested real LLM use with budget below USD 1; selected USD 0.50 total.",
               "note": "One retained allowance for trial and console together. Restarting does not renew it."}
    if project_ceiling is not None:
        payload.update(version='live-allowance-v2',cap_usd=project_ceiling,baseline_project_usd=0.0,
            ceiling_project_usd=project_ceiling,
            authorization='Explicit CLI --allow-paid --max-usd-total project ceiling; includes all prior spend and reservations.',
            note='Absolute project ceiling, not an additional allowance. Historical trial authorization remains unchanged.')
    try:
        with path.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        read_allowance(path, runs_dir)  # another authorized console won; do not renew the grant
    return path


def read_allowance(path: Path, runs_dir: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not all(isinstance(data.get(k), (float, int)) and not isinstance(data[k], bool) and
               math.isfinite(data[k]) and data[k] >= 0
               for k in ("cap_usd", "baseline_project_usd", "ceiling_project_usd")):
        raise ValueError("invalid live allowance amounts")
    version=data.get('version')
    legacy = version=='live-allowance-v1' and data['cap_usd']==CAP_USD
    project = version=='live-allowance-v2' and data['baseline_project_usd']==0 and data['cap_usd']>0
    if (not (legacy or project) or data.get("model") != MODEL or
        data.get("runs_dir") != str(runs_dir.resolve()) or
        abs(data['ceiling_project_usd']-data['baseline_project_usd']-data['cap_usd'])>1e-9):
        raise ValueError("invalid live allowance identity or ceiling")
    spent = max(0.0, project_spend(runs_dir) - data["baseline_project_usd"])
    return data | {"spent_usd": spent, "remaining_usd": max(0.0, data['cap_usd'] - spent)}


def constrain(config: RunConfig, path: Path, runs_dir: Path) -> RunConfig:
    data = read_allowance(path, runs_dir)
    if data["remaining_usd"] <= .000001:
        raise ValueError("live allowance exhausted; no new paid call is permitted")
    raw = config.model_dump(mode="json")
    raw["llm"]["model"] = MODEL
    configured_reasoning = raw["llm"]["reasoning_max_tokens"]
    raw["llm"]["reasoning_max_tokens"] = min(12000 if configured_reasoning is None else configured_reasoning,
                                                raw["llm"]["max_tokens_per_call"] - 1)
    raw["budget"]["max_usd_total"] = min(raw["budget"]["max_usd_total"], data["ceiling_project_usd"])
    if data['version']=='live-allowance-v2':
        # Explicit absolute authorization supersedes old default config caps, never recorded spend.
        raw['budget']['max_usd_total']=data['ceiling_project_usd']
        raw['budget']['max_usd_current_sprint']=data['ceiling_project_usd']
    raw["budget"]["max_usd_per_investigation"] = min(raw["budget"]["max_usd_per_investigation"], .15,
                                                    data["remaining_usd"])
    return RunConfig.model_validate(raw)
