"""Read-only restart and sanitized-log acceptance for the existing Phase 5 job."""
from __future__ import annotations
import json
import subprocess
import time
from monitor_api import connection, ROOT


def main():
    output = ROOT/"docs"/"production_phase5"
    saved = json.loads((output/"acceptance.json").read_text())
    old_trace = json.loads((output/"trace.json").read_text())
    request = connection()
    deadline = time.monotonic() + 60
    while True:
        try:
            if request("/health/ready")["status"] == "ready":
                break
        except (OSError, RuntimeError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("Service did not become ready after restart")
        time.sleep(2)
    job = saved["job_id"]
    status = request(f"/api/v1/jobs/{job}")
    result = request(f"/api/v1/jobs/{job}/results")
    trace = request(f"/api/v1/jobs/{job}/trace")
    catalog = request("/api/v1/capabilities")
    assert len(catalog["tools"]) == 18 and all(tool["available"] for tool in catalog["tools"])
    assert status["state"] == "completed"
    assert {k:v for k,v in result.items() if k != "job_id"} == saved["result"]
    assert trace["spans"][:len(old_trace["spans"])] == old_trace["spans"]
    logs = subprocess.run(["docker", "logs", "blackgrid-blackgrid-1"], capture_output=True, check=True).stdout.decode()
    for name in ("alice.token", "openrouter-key.txt", "server-key.pem"):
        path = ROOT/".secrets"/name
        if path.is_file():
            secret = path.read_text().strip()
            assert not secret or secret not in logs, "Secret found in service logs"
    events = [json.loads(line) for line in logs.splitlines() if line.startswith("{")]
    assert any(e.get("tool") == "community_test" and "analysis" in e for e in events)
    assert any(e.get("component") == "api" and e.get("job_id") == job for e in events)
    evidence = dict(post_restart_ready=True, completed_result_exact=True, original_trace_prefix_exact=True,
        service_log_records=len(events), known_secrets_absent=True, tool_analysis_logged=True,
        request_job_correlation_logged=True, registered_tools_available=18, new_jobs_submitted=0, paid_calls=0)
    (output/"restart_verification.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
