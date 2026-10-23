"""Offline-only acceptance against the existing local Compose service."""
from __future__ import annotations
import argparse
import json
import math
import time
import uuid
from pathlib import Path
from monitor_api import connection, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    request = connection()
    output = ROOT / "docs" / "production_phase5"
    output.mkdir(parents=True, exist_ok=True)
    times = []
    for _ in range(30):
        before = time.perf_counter()
        assert request("/health/ready")["status"] == "ready"
        times.append(time.perf_counter() - before)
        time.sleep(.05)
    start = time.perf_counter()
    # Always mock: this script cannot authorize a provider request.
    job = request("/api/v1/jobs", {"mode": "mock", "question": "Does this network show stronger community structure than expected from node degrees?"},
                  "phase5-"+uuid.uuid4().hex)["job_id"]
    deadline = time.monotonic() + 960
    while time.monotonic() < deadline:
        status = request(f"/api/v1/jobs/{job}")
        if status["state"] not in ("running", "queued"):
            break
        time.sleep(2)
    assert status["state"] == "completed", status
    duration = time.perf_counter() - start
    result = request(f"/api/v1/jobs/{job}/results")
    assert result["summary"]["actual_usd"] == 0
    times.sort()
    evidence = {"job_id": job, "mode": "mock", "paid_calls": 0, "health_samples": len(times),
        "health_seconds": {f"p{q}": times[math.ceil(len(times)*q/100)-1] for q in (50,95,99)},
        "job_wall_seconds": duration, "result": {k:v for k,v in result.items() if k != "job_id"}}
    if not args.baseline:
        baseline = json.loads((output / "baseline.json").read_text())
        assert baseline["result"] == evidence["result"], "Scientific API result changed"
        trace = request(f"/api/v1/jobs/{job}/trace")
        assert trace["available"] and not trace["open_span_ids"]
        names = {s["name"] for s in trace["spans"]}
        assert {"job_scheduling", "agent_execution", "llm_call", "provider_request", "tool_call", "artifact_persistence"} <= names
        evidence["trace_names"] = sorted(names)
        evidence["exact_api_result_parity"] = True
        # Wait out the bounded cache; snapshots never influence job execution.
        snapshot = request("/api/v1/monitoring.json")
        if not snapshot["tool"]:
            time.sleep(10)
            snapshot = request("/api/v1/monitoring.json")
        assert snapshot["scheduler_available"] and snapshot["tool"]
        metrics = request("/api/v1/metrics", raw=True)
        assert "blackgrid_http_requests_total" in metrics and "blackgrid_recent_tool_duration_seconds_sum" in metrics
        page = request("/api/v1/monitoring", raw=True)
        assert "Tool bottlenecks" in page
        (output / "dashboard.html").write_text(page, encoding="utf-8")
        (output / "monitoring.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        (output / "metrics.prom").write_text(metrics, encoding="utf-8")
        (output / "trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    name = "baseline.json" if args.baseline else "acceptance.json"
    (output / name).write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in evidence.items() if k != "result"}, indent=2))


if __name__ == "__main__":
    main()
