"""Operator browser sessions and bounded live dashboard projections."""
from __future__ import annotations
import collections
import hashlib
import json
import math
import re
import secrets
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

COOKIE = "blackgrid_dashboard"
PATH = "/api/v1/dashboard"
ASSETS = Path(__file__).with_name("dashboard_assets")


class Sessions:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.entries = {}
        self.ttl = 900

    def issue(self, owner):
        with self.lock:
            now = self.clock()
            self.entries = {k:v for k,v in self.entries.items() if v[1] > now}
            if len(self.entries) >= 128 or sum(v[0] == owner for v in self.entries.values()) >= 4:
                return None
            token = secrets.token_urlsafe(32)
            self.entries[hashlib.sha256(token.encode()).hexdigest()] = (owner, now+self.ttl)
            return token

    def owner(self, token):
        if not token or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            return None
        with self.lock:
            key = hashlib.sha256(token.encode()).hexdigest()
            entry = self.entries.get(key)
            if entry and entry[1] > self.clock():
                return entry[0]
            self.entries.pop(key, None)
            return None

    def revoke(self, token):
        if isinstance(token, str):
            with self.lock:
                self.entries.pop(hashlib.sha256(token.encode()).hexdigest(), None)


class LiveView:
    def __init__(self):
        self.lock = threading.Lock()
        self.points = collections.deque(maxlen=720)
        self.previous = None

    def project(self, snapshot, requests):
        with self.lock:
            now = time.monotonic()
            cpu = snapshot["resources"].get("cpu_usage_seconds")
            if self.previous is None or now-self.previous[0] >= 5:
                rate = utilization = None
                if self.previous:
                    before, total, old_cpu = self.previous
                    rate = max(0., requests-total)/(now-before)
                    if cpu is not None and old_cpu is not None:
                        utilization = 100*max(0., cpu-old_cpu)/(now-before)
                self.points.append(dict(timestamp=datetime.now(UTC).isoformat(),
                    requests_per_second=rate, cpu_percent_of_one_core=utilization,
                    memory_bytes=snapshot["resources"]["memory_current_bytes"],
                    queued=snapshot["jobs"]["queued"], running=snapshot["jobs"]["running"],
                    completed=snapshot["jobs"]["completed"],
                    api_p50_seconds=snapshot["api"]["p50_seconds"],
                    api_p95_seconds=snapshot["api"]["p95_seconds"],
                    api_p99_seconds=snapshot["api"]["p99_seconds"],
                    charged_usd=snapshot["charged_usd"], held_usd=snapshot["reserved_or_held_usd"]))
                self.previous = now, requests, cpu
            return list(self.points)


def benchmark_status(root):
    """Only fixed, bounded aggregate schema; no report path/content is forwarded."""
    if root is None:
        return None
    path = root / "status.json"
    try:
        if root.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size > 1024**2:
            return None
        value = json.loads(path.read_bytes())
        if value.get("version") not in ("production-phase6-v1", "production-phase6-v2") or value.get("state") not in ("running", "completed", "stopped", "failed"):
            return None
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value.get("run_id", "")):
            return None
        result = {k:value[k] for k in ("version", "state", "run_id")}
        for key in ("users", "elapsed_s"):
            item = value.get(key)
            if type(item) not in (int,float) or not math.isfinite(item) or not 0 <= item <= 10_000:
                return None
            result[key] = item
        if value.get("category") not in ("api", "mixed", "tools", "mock"):
            return None
        result["category"] = value["category"]
        result["counts"] = {}
        for key in ("requests", "accepted", "rejected", "completed", "failed", "censored", "rate_limited", "unexpected_errors"):
            item = value.get("counts", {}).get(key, 0)
            if type(item) is not int or not 0 <= item <= 10_000_000:
                return None
            result["counts"][key] = item
        result["series"] = []
        for point in value.get("series", [])[-360:]:
            safe = {}
            for key in ("elapsed_s", "users", "requests", "accepted", "completed", "rejected", "cpu_percent", "memory_bytes", "p95_ms"):
                item = point.get(key)
                if item is None:
                    safe[key] = None
                elif type(item) in (float,int) and math.isfinite(item) and 0 <= item <= 1e15:
                    safe[key] = item
                else:
                    return None
            result["series"].append(safe)
        return result
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None
