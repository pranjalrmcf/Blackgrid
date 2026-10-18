"""Scientific fingerprint of a run, for parity checks across implementations (Sprint 2).

The fingerprint keeps what must not change when orchestration changes: graph identity, the full
experiment and sensitivity outputs, verdict, flags, required-analysis outcome, accepted claims,
and LLM call/token counters. It drops timings, run IDs, timestamps, and trace metadata.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

VOLATILE_KEYS = {"elapsed_s", "created_utc", "finished_utc", "run_id", "fetched_utc"}


def _strip(value: object) -> object:
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def _load(run_dir: Path, name: str) -> dict | None:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def fingerprint(run_dir: Path) -> dict:
    inv = _load(run_dir, "investigation.json") or {}
    exp = _load(run_dir, "experiment_report.json")
    sens = _load(run_dir, "sensitivity.json")
    record = _load(run_dir, "graph_record.json") or {}
    primary = (exp or {}).get("primary") or {}
    result = primary.get("result") or {}
    cost = inv.get("cost") or {}
    return {
        "projection_sha256": record.get("projection_sha256"),
        "experiment_sha256": _digest(_strip(exp)) if exp else None,
        "sensitivity_sha256": _digest(_strip(sens)) if sens else None,
        "observed_q": result.get("observed_statistic"),
        "null_mean": (result.get("null") or {}).get("mean"),
        "p_value": result.get("p_value"),
        "exceedances": result.get("exceedances"),
        "sensitivity_agreement": (sens or {}).get("agreement"),
        "status": inv.get("status"),
        "verdict": inv.get("verdict"),
        "flags": sorted(inv.get("flags") or []),
        "missing_analyses": list(inv.get("missing_analyses") or []),
        "accepted_claims": [c.get("text") for c in inv.get("reported_claims") or []],
        "rejected_claims": sorted(str((d.get("claim") or {}).get("text")) for d in inv.get("critic_decisions") or []
                                  if not d.get("accepted")),
        "llm_calls": cost.get("llm_calls"),
        "tokens_in": cost.get("input_tokens"),
        "tokens_out": cost.get("output_tokens"),
        "actual_usd": cost.get("actual_usd"),
    }


def compare(reference: dict, candidate: dict) -> list[str]:
    """Differences between two fingerprints (empty means parity)."""
    return [f"{key}: reference={reference.get(key)!r} candidate={candidate.get(key)!r}"
            for key in sorted(set(reference) | set(candidate)) if reference.get(key) != candidate.get(key)]
