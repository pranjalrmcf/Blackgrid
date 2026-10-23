"""Verify the existing local Compose API without printing or logging credentials."""
from __future__ import annotations

import argparse
import json
import re
import ssl
import subprocess
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="alice")
    parser.add_argument("--reference-run", type=Path)
    parser.add_argument("--check-queue", action="store_true", help="Verify Phase 4 waiting cancellation and tool progress")
    parser.add_argument("--check-tools", action="store_true", help="Verify automatic routing across all analysis families")
    parser.add_argument("--output", type=Path, default=Path("docs/production_phase3/service_integration/verification.json"))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.subject):
        parser.error("invalid client subject")
    root = Path(__file__).resolve().parents[1]
    # Client material is read only in memory, never passed as a process argument.
    token = (root / ".secrets" / (args.subject + ".token")).read_text().strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
        parser.error("invalid client token file")
    context = ssl.create_default_context(cafile=str(root / ".secrets/server-cert.pem"))
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context))
    evidence = {"status": "running", "checks": {}, "paid_usd": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(evidence, indent=2) + "\n")

    def check(name, value):
        evidence["checks"][name] = value
        save()
        print(name, json.dumps(value), flush=True)

    def docker(*argv):
        result = subprocess.run(["docker", *argv], cwd=root, capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise RuntimeError("Docker verification command failed")
        return result.stdout

    key = "service-check-" + uuid.uuid4().hex
    def request(method, path, body=None, authenticated=True):
        headers = {"Idempotency-Key": key}
        if authenticated:
            headers["Authorization"] = "Bearer " + token
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request("https://localhost:8765" + path, data=data, headers=headers, method=method)
        try:
            reply = opener.open(req, timeout=10)
        except HTTPError as exc:
            reply = exc
        with reply:
            return reply.status, json.loads(reply.read()), reply.headers

    def ready():
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            try:
                if request("GET", "/health/ready", authenticated=False)[0] == 200:
                    return
            except (OSError, URLError):
                pass
            time.sleep(1)
        raise RuntimeError("API readiness timeout")

    try:
        inspected = json.loads(docker("inspect", "blackgrid-blackgrid-1"))[0]
        host = inspected["HostConfig"]
        assert inspected["Config"]["Cmd"] == ["api"] and inspected["Config"]["User"] == "10001:10001"
        assert host["ReadonlyRootfs"] and host["CapDrop"] == ["ALL"]
        assert host["Memory"] == 2 * 1024**3 and host["PidsLimit"] == 128
        assert host["PortBindings"]["8765/tcp"] == [{"HostIp": "127.0.0.1", "HostPort": "8765"}]
        mounts = inspected["Mounts"]
        state = next(m for m in mounts if m["Destination"] == "/app/runs")
        assert state["Name"] == "blackgrid_blackgrid-state"
        for destination in ("/app/data", "/run/secrets/clients.json", "/run/secrets/server-cert.pem",
                            "/run/secrets/server-key.pem"):
            assert not next(m for m in mounts if m["Destination"] == destination)["RW"]
        network = next(iter(inspected["NetworkSettings"]["Networks"]))
        assert json.loads(docker("network", "inspect", network))[0]["Driver"] == "bridge"
        assert inspected["NetworkSettings"]["Ports"]["8765/tcp"] == [{"HostIp": "127.0.0.1", "HostPort": "8765"}]
        probe = """from blackgrid.operations.worker import deny_network
import socket, errno
assert deny_network() == 'seccomp_network_denied'
try:
    socket.socket()
except OSError as exc:
    assert exc.errno == errno.EPERM
else:
    raise AssertionError('socket unexpectedly allowed')
"""
        docker("exec", "blackgrid-blackgrid-1", "python", "-c", probe)
        check("runtime", {"same_state_volume": state["Name"], "non_root": True, "read_only": True,
                          "localhost_only_port": True, "worker_network_denied": True, "read_only_secrets": True})
        ready()
        status, _, headers = request("GET", "/health/ready", authenticated=False)
        assert status == 200 and headers.get("Strict-Transport-Security")
        assert request("GET", "/api/v1/openapi.json", authenticated=False)[0] == 401
        assert request("GET", "/api/v1/openapi.json")[0] == 200
        check("https_auth_readiness", True)
        status, job, _ = request("POST", "/api/v1/jobs", {})
        assert status == 202
        job_id = job["job_id"]
        assert request("POST", "/api/v1/jobs", {})[0] == 200
        assert request("POST", "/api/v1/jobs", {"condition": "tool_only"})[0] == 409
        if args.check_queue:
            original_key = key
            key = "waiting-check-" + uuid.uuid4().hex
            status, waiting, _ = request("POST", "/api/v1/jobs", {})
            assert status == 202 and waiting["state"] == "queued"
            status, cancelled, _ = request("POST", f"/api/v1/jobs/{waiting['job_id']}/cancel", {})
            assert status == 200 and cancelled["state"] == "cancelled" and cancelled["attempts"] == 0
            assert cancelled["completed_utc"] and cancelled["progress"]["reserved_usd"] == 0
            key = original_key
            check("queued_cancel_without_dispatch", True)
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            status, job, _ = request("GET", "/api/v1/jobs/" + job_id)
            assert status == 200
            if job["state"] not in ("queued", "running"):
                break
            time.sleep(2)
        assert job["state"] == "completed", "offline job did not complete"
        if args.check_queue:
            assert job["started_utc"] and job["completed_utc"] and job["attempts"] == 1
            assert job["result_ref"] == f"/api/v1/jobs/{job_id}/results"
            tools = job["progress"]["tools"]
            assert {item["tool"] for item in tools} >= {"profile_graph", "community_test", "edge_removal_sensitivity"}
            assert all(item["state"] == "succeeded" and item["analysis"] for item in tools)
            check("lifecycle_and_tool_progress", {"attempts": 1, "timestamps": True,
                                                  "tools": [item["tool"] for item in tools]})
        status, result, _ = request("GET", f"/api/v1/jobs/{job_id}/results")
        assert status == 200 and result["summary"]["actual_usd"] == 0
        assert request("GET", f"/api/v1/jobs/{job_id}/artifacts/summary.json")[0] == 200
        assert request("GET", f"/api/v1/jobs/{job_id}/artifacts/manifest.json")[0] == 404
        check("offline_job", {"job_id": job_id, "state": job["state"], "summary": result["summary"]})
        if args.reference_run:
            from blackgrid.analysis.parity import fingerprint
            reference = fingerprint(args.reference_run)
            # Auto routing changes the planner request's family token. Compare
            # scientific outputs/call count/cost, rather than that token count.
            keys = set(result["summary"]) - {"tokens_in", "tokens_out"}
            assert {k: result["summary"][k] for k in keys} == {k: reference[k] for k in keys}
            check("scientific_summary_matches_host_reference", True)
        docker("compose", "restart", "--timeout", "40", "blackgrid")
        ready()
        status, replay, _ = request("POST", "/api/v1/jobs", {})
        assert status == 200 and replay["job_id"] == job_id and replay["state"] == "completed"
        assert request("GET", f"/api/v1/jobs/{job_id}/results")[1] == result
        check("restart_preserves_job_results_and_idempotency", True)
        if args.check_tools:
            from blackgrid.operations.api_tools import CATALOG
            status, catalog, _ = request("GET", "/api/v1/capabilities")
            assert status == 200 and {t["name"] for t in catalog["tools"]} == set(CATALOG)
            assert all(t["available"] for t in catalog["tools"])
            check("all_18_tools_configured", True)
            questions = {
                "centrality": "Which nodes have highest degree and betweenness?",
                "bridge": "Which nodes bridge separate communities?",
                "behavior": "Cluster behavioral profiles and find similar users and unusual activity candidates.",
                "research": "Review Sprint 7 uncertainty, posterior beliefs, next experiment and causal identification.",
                "forecast": "Which pairs who have never messaged will message next month, and how reliable is the ranking?",
            }
            for family, question in questions.items():
                key = "tool-check-" + uuid.uuid4().hex
                status, job, _ = request("POST", "/api/v1/jobs", {"question": question})
                assert status == 202
                job_id = job["job_id"]
                deadline = time.monotonic() + 950
                while time.monotonic() < deadline:
                    _, job, _ = request("GET", f"/api/v1/jobs/{job_id}")
                    if job["state"] not in ("queued", "running"):
                        break
                    time.sleep(2)
                assert job["state"] == "completed", f"{family} did not complete: {job['state']}"
                status, result, _ = request("GET", f"/api/v1/jobs/{job_id}/results")
                assert status == 200 and result["family"] == family and result["summary"]["actual_usd"] == 0
                if family == "research":
                    assert result["research_verification_profile"] == "api-beliefs-portability-v1"
                assert result["analyses"] and "1000001" not in json.dumps(result)
                check("automatic_" + family, {"state": job["state"], "family": result["family"],
                    "tools": list(result["analyses"]), "claim_type": result["claim_type"], "scope": result["scope"]})
        evidence["status"] = "passed"
    except Exception as exc:
        evidence.update(status="failed", failure=type(exc).__name__)
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
