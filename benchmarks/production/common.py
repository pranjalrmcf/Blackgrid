"""Independent numerical summaries and resource stops for the frozen pilot."""
import json
import math
from pathlib import Path


def quantiles(values):
    data = sorted(values)
    if any(not math.isfinite(v) or v < 0 for v in data):
        raise ValueError("invalid benchmark measurement")
    return {"samples": len(data), **{f"p{q}": data[max(0,math.ceil(len(data)*q/100)-1)] if data else None
                                   for q in (50,95,99)}}


def stop_reason(resources, protocol):
    for field, ceiling in (("memory_current_bytes", "target_memory_stop_bytes"), ("pids_current", "target_pids_stop")):
        if resources.get(field) is not None and resources[field] >= protocol[ceiling]:
            return "resource_threshold"
    if resources.get("disk_free_bytes") is not None and resources["disk_free_bytes"] < protocol["disk_free_stop_bytes"]:
        return "storage_threshold"
    return None


def atomic_json(path, value):
    path = Path(path)
    pending = path.with_suffix(path.suffix+".pending")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")
    pending.replace(path)
