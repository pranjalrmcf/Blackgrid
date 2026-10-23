"""Authenticated local monitoring projections, never raw scientific records."""
from __future__ import annotations

import collections
import html
import json
import math
import sqlite3
import threading
import time
import shutil
from pathlib import Path
from contextlib import closing
from datetime import UTC, datetime

from blackgrid.operations import telemetry
from blackgrid.operations.api_tools import CATALOG, read_artifact

BUCKETS = (.01, .05, .1, .25, .5, 1., 2., 5., 10., 30., 120., 300., 930., float("inf"))
STATES = {"queued", "running", "completed", "failed", "cancelled", "abstained", "partial",
          "timed_out", "paused", "interrupted"}
CATEGORIES = {"malformed", "permanent", "transient", "uncertain", "replay_mismatch", "rejected", "answer_key"}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def elapsed(start, end):
    try:
        return max(0., (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    except (ValueError, TypeError):
        return None


class Monitoring:
    def __init__(self):
        self.lock = threading.RLock()
        self.cache_lock = threading.Lock()
        self.active = 0
        self.requests = collections.Counter()
        self.latencies = collections.defaultdict(lambda: [0.] * (len(BUCKETS) + 1))
        self.recent = collections.deque(maxlen=2048)
        self.cached = None
        self.cache_time = 0.

    def begin(self):
        with self.lock:
            self.active += 1

    def finish(self, route, status, duration):
        with self.lock:
            self.active -= 1
            self.requests[route, status] += 1
            bins = self.latencies[route]
            for i, boundary in enumerate(BUCKETS):
                bins[i] += int(duration <= boundary)
            bins[-1] += duration
            self.recent.append((time.monotonic(), status, duration))

    def snapshot(self, jobs):
        with self.cache_lock:
            # Serialize refreshes, bound I/O and avoid reopening databases for every poll.
            if self.cached is None or time.monotonic() - self.cache_time >= 10:
                self.cached = self._durable(jobs)
                self.cache_time = time.monotonic()
            result = dict(self.cached)
        with self.lock:
            window = [r for r in self.recent if time.monotonic() - r[0] <= 300]
            durations = sorted(r[2] for r in window)
            result["api"] = {"active_requests": self.active, "window_seconds": 300,
                "window_samples": len(window), "window_capacity": 2048,
                "request_rate_per_second": len(window) / 300,
                "error_fraction": sum(r[1] >= 500 for r in window) / len(window) if window else None,
                **{f"p{q}_seconds": durations[max(0, math.ceil(len(durations)*q/100)-1)] if durations else None
                   for q in (50, 95, 99)}}
            result["telemetry_write_failures_process"] = telemetry.WRITE_FAILURES
            result["resources"] = resources(jobs.root)
            result["alerts"] = alerts(result)
            return result

    def _durable(self, jobs):
        result = dict(observed_utc=datetime.now(UTC).isoformat(), scheduler_available=not jobs.stopping and not jobs.scheduler_failed,
            database_available=True, jobs={s: 0 for s in sorted(STATES)}, recoveries=0,
            charged_usd=0., settled_usd=0., reserved_or_held_usd=0., budget_used_usd=None,
            budget_ceiling_usd=None, queue_oldest_seconds=0., queue_wait_seconds=[],
            completion_seconds=[], tool={}, llm=dict(calls=0, input_tokens=0, output_tokens=0,
                actual_or_assumed_usd=0., reservation_estimate_usd=0., retries=0, errors={},
                provider=None, model=None, ttft_seconds=None, generation_tokens_per_second=None),
            sample_jobs=0, sample_limit=100, workflow_read_failures=0, traces_missing=0,
            worker_peak_rss_bytes=None, graph_nodes=[], graph_edges=[], llm_seconds=[],
            provider_seconds=[], tool_selection_rejections=0, workflow_tool_failures=0)
        result["llm"]["rate_limits"] = 0
        result.update(agent_completion_fraction=None, cost_per_successful_live_analysis_usd=None)
        try:
            with closing(jobs.db()) as db:
                db.row_factory = sqlite3.Row
                rows = [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 5000")]
                if jobs.live_policy:
                    result["budget_used_usd"] = jobs.live_usage(db)
                    result["budget_ceiling_usd"] = jobs.live_policy.ceiling_project_usd
                    # Fixed server policy, not a model response or arbitrary metric label.
                    result["llm"].update(provider="openrouter", model=jobs.live_policy.model)
        except sqlite3.Error:
            result["database_available"] = False
            result["scheduler_available"] = False
            return result
        for row in rows:
            if row["state"] in STATES:
                result["jobs"][row["state"]] += 1
            result["recoveries"] += max(0, row["attempts"] - 1)
            result["charged_usd"] += row["charged_usd"]
            if row["billing"] == "settled":
                result["settled_usd"] += row["charged_usd"]
            if row["billing"] in ("reserved", "held"):
                result["reserved_or_held_usd"] += max(row["charged_usd"], row["reserved_usd"])
            if row["state"] == "queued":
                result["queue_oldest_seconds"] = max(result["queue_oldest_seconds"],
                    elapsed(row["created"], datetime.now(UTC).isoformat()) or 0.)
            for key, end in (("queue_wait_seconds", row["started"]), ("completion_seconds", row["finished"])):
                seconds = elapsed(row["created"], end)
                if seconds is not None:
                    result[key].append(seconds)
        for row in rows[:100]:
            result["sample_jobs"] += 1
            folder = jobs.folder(row["owner"], row["id"])
            spans = telemetry.read_spans(folder / "telemetry.jsonl")
            if not spans:
                result["traces_missing"] += 1
            for record in spans:
                if record["event"] == "end" and record["name"] == "provider_rate_limit":
                    result["llm"]["rate_limits"] += 1
                if record["event"] == "end" and record["name"] == "tool_selection_failure":
                    result["tool_selection_rejections"] += 1
                if record["event"] == "end" and record["name"] in ("llm_call", "provider_request"):
                    result["llm_seconds" if record["name"] == "llm_call" else "provider_seconds"].append(record["duration_s"])
                if record["name"] in ("llm_call", "tool_call", "artifact_persistence"):
                    result["worker_peak_rss_bytes"] = max(result["worker_peak_rss_bytes"] or 0, record["peak_rss_bytes"])
            database = folder / "workflow.sqlite"
            if not database.is_file() or database.is_symlink():
                continue
            try:
                with closing(sqlite3.connect(database.resolve().as_uri()+"?mode=ro", uri=True, timeout=.1)) as db:
                    operations = db.execute("SELECT kind,name,state,category,attempt,prompt_tokens,completion_tokens,actual_usd,reserved_usd,records_json FROM operations LIMIT 1000").fetchall()
                for kind, name, state, category, attempt, inp, out, cost, reserve, records in operations:
                    if kind == "llm":
                        stats = result["llm"]
                        stats["calls"] += 1
                        stats["input_tokens"] += inp
                        stats["output_tokens"] += out
                        stats["actual_or_assumed_usd"] += cost
                        stats["reservation_estimate_usd"] += reserve
                        stats["retries"] += int(attempt > 0)
                        if category in CATEGORIES:
                            stats["errors"][category] = stats["errors"].get(category, 0) + 1
                    elif kind == "tool" and name in CATALOG:
                        stats = result["tool"].setdefault(name, dict(succeeded=0, failed=0, seconds=[]))
                        stats["succeeded"] += int(state == "succeeded")
                        stats["failed"] += int(state == "failed_known")
                        result["workflow_tool_failures"] += int(state == "failed_known")
                        result["tool_selection_rejections"] += int(category == "rejected")
                        for record in json.loads(records or "[]"):
                            if record.get("tool") == name and finite(record.get("elapsed_s")):
                                stats["seconds"].append(record["elapsed_s"])
                run = jobs.run_folder(row["owner"], row["id"])
                graph = read_artifact(run, "graph_record.json") if run else None
                if graph:
                    for key, field in (("graph_nodes", "active_nodes"), ("graph_edges", "unique_edges")):
                        if finite(graph.get(field)):
                            result[key].append(graph[field])
            except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
                result["workflow_read_failures"] += 1
        finished = sum(result["jobs"][s] for s in STATES - {"queued", "running"})
        result["agent_completion_fraction"] = result["jobs"]["completed"] / finished if finished else None
        # Only costs belonging to completed jobs; failures/holds are separately visible.
        successful = [r for r in rows if r["state"] == "completed" and r["mode"] == "live" and r["billing"] == "settled"]
        result["cost_per_successful_live_analysis_usd"] = sum(r["charged_usd"] for r in successful) / len(successful) if successful else None
        return result

    def prometheus(self, snapshot):
        lines = []
        def gauge(name, value, labels=""):
            if value is not None:
                lines.append(f"blackgrid_{name}{labels} {float(value):.12g}")
        def histogram(name, values, labels=""):
            # Durable rolling projections are gauges, not monotonic counters.
            for boundary in BUCKETS:
                label = "+Inf" if math.isinf(boundary) else str(boundary)
                suffix = labels[1:-1] + "," if labels else ""
                gauge(name+"_bucket", sum(v <= boundary for v in values), '{'+suffix+f'le="{label}"'+'}')
            gauge(name+"_count", len(values), labels)
            gauge(name+"_sum", sum(values), labels)
        with self.lock:
            for (route, status), count in sorted(self.requests.items()):
                gauge("http_requests_total", count, '{route='+json.dumps(route)+f',status="{status}"'+'}')
            for route, bins in sorted(self.latencies.items()):
                for i, boundary in enumerate(BUCKETS):
                    label = "+Inf" if math.isinf(boundary) else str(boundary)
                    gauge("http_request_duration_seconds_bucket", bins[i], '{route='+json.dumps(route)+',le="'+label+'"}')
                gauge("http_request_duration_seconds_count", bins[-2], '{route='+json.dumps(route)+'}')
                gauge("http_request_duration_seconds_sum", bins[-1], '{route='+json.dumps(route)+'}')
        gauge("http_active_requests", snapshot["api"]["active_requests"])
        for key, value in snapshot["resources"].items():
            gauge("resource_"+key, value)
        for state, count in snapshot["jobs"].items():
            gauge("jobs", count, '{state="'+state+'"}')
        for key in ("scheduler_available", "database_available", "recoveries", "charged_usd", "settled_usd",
                    "reserved_or_held_usd", "budget_used_usd", "budget_ceiling_usd", "queue_oldest_seconds",
                    "sample_jobs", "workflow_read_failures", "traces_missing", "worker_peak_rss_bytes",
                    "agent_completion_fraction", "cost_per_successful_live_analysis_usd", "telemetry_write_failures_process",
                    "tool_selection_rejections", "workflow_tool_failures"):
            gauge(key, snapshot[key])
        for key in ("queue_wait_seconds", "completion_seconds", "llm_seconds", "provider_seconds", "graph_nodes", "graph_edges"):
            histogram("recent_"+key, snapshot[key])
        for name, stats in snapshot["tool"].items():
            labels = '{tool="'+name+'"}'
            for key in ("succeeded", "failed"):
                gauge("recent_tool_"+key, stats[key], labels)
            histogram("recent_tool_duration_seconds", stats["seconds"], labels)
        for key in ("calls", "input_tokens", "output_tokens", "actual_or_assumed_usd", "reservation_estimate_usd", "retries", "rate_limits"):
            gauge("recent_llm_"+key, snapshot["llm"][key])
        if snapshot["llm"]["provider"]:
            gauge("llm_info", 1, '{provider='+json.dumps(snapshot["llm"]["provider"])+',model='+json.dumps(snapshot["llm"]["model"])+'}')
        for category, count in snapshot["llm"]["errors"].items():
            gauge("recent_llm_errors", count, '{category="'+category+'"}')
        for alert in snapshot["alerts"]:
            gauge("alert", alert["firing"], '{name="'+alert["name"]+'"}')
        return "\n".join(lines)+"\n"


def alerts(s):
    """Local advisory alerts; no external notifications or automatic paid retries."""
    errors = s["llm"]["errors"]
    return [dict(name=name, firing=bool(value), action=action) for name, value, action in (
        ("storage_unavailable", not s["database_available"], "Check volume and free disk; preserve ledgers."),
        ("scheduler_unavailable", not s["scheduler_available"], "Inspect worker and restart only after reviewing active live jobs."),
        ("queue_pressure", s["jobs"]["queued"] >= 6 or s["queue_oldest_seconds"] > 120, "Review workload; do not raise limits without measurements."),
        ("api_errors", s["api"]["window_samples"] >= 20 and (s["api"]["error_fraction"] or 0) > .05, "Inspect sanitized request categories and readiness."),
        ("provider_failures", sum(errors.get(k, 0) for k in ("permanent", "transient", "uncertain")) > 0, "Review provider and billing holds; never resend uncertain calls."),
        ("budget_pressure", s["budget_ceiling_usd"] is not None and s["budget_used_usd"] >= .8*s["budget_ceiling_usd"], "Review retained project budget before another paid job."),
        ("worker_memory_pressure", (s["worker_peak_rss_bytes"] or 0) > 1.5*1024**3, "Review graph size and algorithm timings."),
        ("storage_pressure", s.get("resources", {}).get("disk_free_bytes") is not None and s["resources"]["disk_free_bytes"] < 1024**3, "Free unrelated disk space; preserve authoritative scientific and billing records."),
        ("telemetry_degraded", s["workflow_read_failures"] or s.get("telemetry_write_failures_process"), "Inspect storage; monitoring failures do not authorize scientific retries."))]


def dashboard(snapshot):
    # Server-rendered, no scripts/CDN/credentials/forms. Browser/API bearer auth required.
    data = html.escape(json.dumps(snapshot, indent=2, sort_keys=True, allow_nan=False))
    def esc(value):
        return html.escape(str(value if value is not None else "unavailable"))
    api, llm = snapshot["api"], snapshot["llm"]
    cards = [("Readiness", snapshot["scheduler_available"] and snapshot["database_available"]),
        ("Queue", snapshot["jobs"]["queued"]), ("Running", snapshot["jobs"]["running"]),
        ("Completed", snapshot["jobs"]["completed"]), ("API p50 / p95 / p99 seconds",
        " / ".join(esc(api[f"p{q}_seconds"]) for q in (50, 95, 99))),
        ("Retained budget used / ceiling USD", f'{snapshot["budget_used_usd"]} / {snapshot["budget_ceiling_usd"]}'),
        ("Recent input / output tokens", f'{llm["input_tokens"]} / {llm["output_tokens"]}'),
        ("Held or reserved USD", snapshot["reserved_or_held_usd"])]
    cards_html = "".join("<tr><th>"+esc(k)+"</th><td>"+esc(v)+"</td></tr>" for k,v in cards)
    rows = sorted(snapshot["tool"].items(), key=lambda p: sum(p[1]["seconds"]), reverse=True)
    tools = "".join("<tr><td>"+esc(name)+"</td><td>"+esc(round(sum(s["seconds"]), 6))+"</td><td>"+str(s["succeeded"])+"</td><td>"+str(s["failed"])+"</td></tr>" for name,s in rows)
    notices = "".join("<li><strong>"+esc(a["name"])+": "+("FIRING" if a["firing"] else "clear")+"</strong> — "+esc(a["action"])+"</li>" for a in snapshot["alerts"])
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>BLACKGRID monitoring</title><h1>BLACKGRID monitoring</h1><p>Local operator view. Refresh to update; durable measurements cached for 10 seconds. API window: at most 2048 requests / 5 minutes. Tool and LLM measurements: newest 100 jobs. Missing measurements are unavailable.</p><p><a href="/api/v1/monitoring">Refresh</a></p><table>'+cards_html+'</table><h2>Tool bottlenecks</h2><table><tr><th>Tool</th><th>Total seconds</th><th>Succeeded</th><th>Failed</th></tr>'+tools+'</table><h2>Advisory alerts</h2><ul>'+notices+'</ul><details><summary>All measurements and coverage</summary><pre>'+data+'</pre></details></html>'


def resources(root):
    result = {"memory_current_bytes": None, "memory_limit_bytes": None, "pids_current": None,
              "pids_limit": None, "disk_free_bytes": None, "cpu_usage_seconds": None, "cpu_throttled_seconds": None}
    for key, name in (("memory_current_bytes", "memory.current"), ("memory_limit_bytes", "memory.max"),
                      ("pids_current", "pids.current"), ("pids_limit", "pids.max")):
        try:
            value = (Path("/sys/fs/cgroup") / name).read_text()[:64].strip()
            if value.isascii() and value.isdecimal():
                result[key] = int(value)
        except OSError:
            pass
    try:
        fields = dict(line.split() for line in Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())
        for key, source in (("cpu_usage_seconds", "usage_usec"), ("cpu_throttled_seconds", "throttled_usec")):
            value = fields.get(source, "")
            if value.isascii() and value.isdecimal():
                result[key] = int(value)/1_000_000
    except (OSError, ValueError):
        pass
    try:
        result["disk_free_bytes"] = shutil.disk_usage(root).free
    except OSError:
        pass
    return result
