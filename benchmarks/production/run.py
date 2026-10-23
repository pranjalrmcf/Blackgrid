"""Headless Locust pilot. Fixed local synthetic target, bounded output and time."""
from gevent import monkey
monkey.patch_all()

import argparse
import hashlib
import importlib.metadata
import json
import os
import random
import resource
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import gevent
import requests
from locust import HttpUser, task, between
from locust.env import Environment
from benchmarks.production.common import atomic_json, quantiles, stop_reason

ROOT = Path("/app")
PROTOCOL_PATH = ROOT/"protocols/production_phase6_v2.json"


def run(category, users, output, seconds=None):
    protocol = json.loads(PROTOCOL_PATH.read_bytes())
    if category not in ("api", "mixed") or users not in protocol["api_users"]:
        raise ValueError("unregistered stage")
    duration = protocol["seconds_per_api_stage" if category == "api" else "seconds_per_mixed_stage"]
    if seconds is not None:
        raise ValueError("changing registered stage duration requires a new protocol")
    output.mkdir(parents=True, exist_ok=False)
    private = json.loads(Path("/run/secrets/benchmark-tokens.json").read_bytes())
    ca = "/run/secrets/server-cert.pem"
    target = "https://127.0.0.1:8765"
    observer = requests.Session()
    observer.trust_env = False
    observer.verify = ca
    observer.headers["Authorization"] = "Bearer "+private[0]["token"]
    identity_response = observer.get(target+"/api/v1/benchmark/identity", timeout=10)
    identity_response.raise_for_status()
    identity = identity_response.json()
    if identity.get("origin") != "synthetic" or identity.get("live_enabled") is not False or identity.get("mock_profile") != "latency":
        raise ValueError("benchmark refuses a non-isolated synthetic mock target")
    start = time.perf_counter()
    random.seed(protocol["seed"]+users)
    stop = None
    samples, jobs, series = [], {}, []
    counts = {k:0 for k in ("requests", "accepted", "rejected", "completed", "failed", "censored", "rate_limited", "unexpected_errors")}
    submit_count = cursor = peak_users = 0
    env = None
    run_id = output.parent.name+"-"+output.name
    status_path = output.parent.parent/"status.json"
    results = {}

    class User(HttpUser):
        wait_time = between(*protocol["think_seconds"])
        def on_start(self):
            nonlocal cursor
            ordinal = cursor
            cursor += 1
            self.rng = random.Random(protocol["seed"]+ordinal+users)
            self.client.trust_env = False
            self.client.verify = ca
            self.ordinal = ordinal+1
            self.client.headers["Authorization"] = "Bearer "+private[self.ordinal]["token"]
            self.pending = None

        @task
        def workflow(self):
            nonlocal submit_count
            age = time.perf_counter()-start
            if category == "api":
                if age < duration and not stop:
                    self.client.get("/api/v1/capabilities", name="capabilities", timeout=10)
                return
            if self.pending:
                job_id = self.pending
                response = self.client.get(f"/api/v1/jobs/{job_id}", name="job_status", timeout=10)
                if response.status_code != 200:
                    return
                row = response.json()
                jobs[job_id].update(state=row["state"], created_utc=row["created_utc"], started_utc=row["started_utc"],
                    completed_utc=row["completed_utc"], attempts=row["attempts"], actual_usd=row["progress"]["actual_usd"])
                if row["state"] not in ("queued", "running"):
                    if row["state"] == "completed":
                        result = self.client.get(f"/api/v1/jobs/{job_id}/results", name="job_results", timeout=10)
                        valid = result.status_code == 200 and result.json().get("summary", {}).get("actual_usd") == 0
                        jobs[job_id]["result_verified"] = valid
                        if valid:
                            jobs[job_id]["tokens_in"] = result.json()["summary"]["tokens_in"]
                            jobs[job_id]["tokens_out"] = result.json()["summary"]["tokens_out"]
                        counts["completed" if valid else "failed"] += 1
                    else:
                        counts["failed"] += 1
                    self.pending = None
                return
            if age >= duration or stop or submit_count >= protocol["max_job_submissions_per_stage"]:
                return
            submit_count += 1
            slot = submit_count
            question = self.rng.choices(protocol["questions"], weights=protocol["workload_weights"])[0]
            # Stable retry identity; no automatic resubmission of an uncertain POST.
            key = "bench-"+run_id+"-"+str(slot)
            with self.client.post("/api/v1/jobs", name="job_submit", json={"mode":"mock", "question":question},
                    headers={"Idempotency-Key":key}, catch_response=True, timeout=10) as response:
                if response.status_code == 202:
                    job_id = response.json()["job_id"]
                    jobs[job_id] = dict(state="queued", owner_ordinal=self.ordinal,
                        submitted_s=time.perf_counter()-start, result_verified=False)
                    self.pending = job_id
                    counts["accepted"] += 1
                elif response.status_code in (429,503):
                    code = response.json().get("error", {}).get("code")
                    if code in ("queue_full", "rate_limited"):
                        response.success()
                        counts["rejected"] += 1
                    else:
                        response.failure("unexpected_service_failure")

    env = Environment(user_classes=[User], host=target)
    @env.events.request.add_listener
    def measured(request_type, name, response_time, response_length, response=None, exception=None, **kwargs):
        nonlocal stop
        counts["requests"] += 1
        status = response.status_code if response is not None else 0
        if status == 429:
            counts["rate_limited"] += 1
        expected = status in (200,202,429)
        if status == 503 and response is not None:
            try:
                expected = response.json().get("error", {}).get("code") == "queue_full"
            except ValueError:
                expected = False
        if not expected:
            counts["unexpected_errors"] += 1
        if len(samples) >= protocol["max_http_samples"]:
            stop = "sample_limit"
        else:
            samples.append(dict(method=request_type, route=name, status=status, milliseconds=response_time,
                                elapsed_s=time.perf_counter()-start))
        if counts["requests"] >= protocol["minimum_error_samples"] and counts["unexpected_errors"]/counts["requests"] > protocol["max_unexpected_error_fraction"]:
            stop = "unexpected_error_rate"

    runner = env.create_local_runner()
    runner.start(users, spawn_rate=users)
    previous_cpu = previous_time = None
    try:
        while True:
            age = time.perf_counter()-start
            peak_users = max(peak_users, runner.user_count)
            if age >= protocol["stage_deadline_seconds"]:
                stop = stop or "deadline"
            try:
                reply = observer.get(target+"/api/v1/monitoring.json", timeout=10)
                reply.raise_for_status()
                snapshot = reply.json()
                if not snapshot["scheduler_available"] or not snapshot["database_available"]:
                    stop = stop or "unhealthy_target"
                resources = snapshot["resources"]
                stop = stop or stop_reason(resources, protocol)
                cpu = resources.get("cpu_usage_seconds")
                cpu_percent = 100*max(0,cpu-previous_cpu)/(age-previous_time) if cpu is not None and previous_cpu is not None and age > previous_time else None
                previous_cpu, previous_time = cpu, age
                series.append(dict(elapsed_s=age, users=runner.user_count, requests=counts["requests"],
                    accepted=counts["accepted"], completed=counts["completed"], rejected=counts["rejected"],
                    cpu_percent=cpu_percent, memory_bytes=resources["memory_current_bytes"],
                    p95_ms=quantiles([s["milliseconds"] for s in samples])["p95"]))
            except (requests.RequestException, ValueError, KeyError):
                stop = stop or "unhealthy_target"
            state = "stopped" if stop else "running"
            atomic_json(status_path, dict(version=protocol["version"], state=state, run_id=run_id,
                category=category, users=runner.user_count, elapsed_s=age, counts=counts, series=series[-360:]))
            pending = sum(j["state"] in ("queued", "running") for j in jobs.values())
            if stop or (age >= duration and (category == "api" or pending == 0)):
                break
            if age >= duration+protocol["drain_seconds"]:
                stop = "drain_deadline"
                break
            gevent.sleep(2)
    finally:
        runner.quit()
    age = time.perf_counter()-start
    for job_id, job in jobs.items():
        if job["state"] in ("queued", "running"):
            counts["censored"] += 1
            # Only explicit safe mock cancellations on the isolated target.
            try:
                observer.post(target+f"/api/v1/jobs/{job_id}/cancel", json={}, timeout=10,
                    headers={"Authorization": "Bearer "+private[job["owner_ordinal"]]["token"]})
            except requests.RequestException:
                pass
    def duration_between(a,b):
        return (datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds() if a and b else None
    waits, completion = [], []
    for job in jobs.values():
        wait = duration_between(job.get("created_utc"), job.get("started_utc"))
        total = duration_between(job.get("created_utc"), job.get("completed_utc"))
        if wait is not None: waits.append(wait)
        if total is not None: completion.append(total)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    summary = dict(version=protocol["version"], run_id=run_id, category=category,
        state="stopped" if stop else "completed", stop_reason=stop, mode="mock", origin="synthetic",
        protocol_sha256=hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest(), identity=identity,
        configured_users=users, observed_peak_users=peak_users, offered_submissions=submit_count,
        offered_seconds=duration, elapsed_s=age, counts=counts, api_latency_ms=quantiles([s["milliseconds"] for s in samples]),
        queue_wait_seconds=quantiles(waits), creation_to_terminal_seconds=quantiles(completion),
        completed_analyses_per_minute=counts["completed"]*60/age, requests_per_second=counts["requests"]/age,
        jobs=jobs, generator_cpu_seconds=usage.ru_utime+usage.ru_stime,
        generator_peak_rss_bytes=usage.ru_maxrss*1024, actual_usd=0,
        versions={name:importlib.metadata.version(name) for name in ("locust", "networkx", "numpy", "scipy")},
        limitations=["small exploratory engineering pilot", "closed-loop users", "synthetic only", "scripted mock latency", "one target worker", "no real provider speed or quality claim"])
    summary["route_latency_ms"] = {name: quantiles([s["milliseconds"] for s in samples if s["route"] == name])
                                   for name in sorted({s["route"] for s in samples})}
    summary["agent_worker_seconds"] = quantiles([duration_between(j.get("started_utc"), j.get("completed_utc"))
        for j in jobs.values() if j.get("started_utc") and j.get("completed_utc")])
    summary["tokens_in"] = sum(j.get("tokens_in",0) for j in jobs.values())
    summary["tokens_out"] = sum(j.get("tokens_out",0) for j in jobs.values())
    atomic_json(output/"summary.json", summary)
    atomic_json(output/"http_samples.json", samples)
    atomic_json(output/"resource_series.json", series)
    atomic_json(status_path, dict(version=protocol["version"], state=summary["state"], run_id=run_id,
        category=category, users=peak_users, elapsed_s=age, counts=counts, series=series[-360:]))
    print(json.dumps({k:summary[k] for k in ("run_id", "state", "configured_users", "observed_peak_users", "counts", "elapsed_s", "stop_reason")}))
    return 2 if stop else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=("api","mixed","tools"), required=True)
    parser.add_argument("--users", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.category == "tools":
        from benchmarks.production.tools import graph_bench, mock_bench
        args.output.mkdir(parents=True, exist_ok=False)
        rows = graph_bench(Path("/bench/public"), args.output)
        mock_bench(args.output)
        print(json.dumps({"tool_samples":len(rows),"mode":"mock","actual_usd":0}))
    else:
        raise SystemExit(run(args.category, args.users, args.output))
