"""Offline Docker acceptance checks; leaves owned state for local inspection.

Requires an already-built production image and a completed current-source host run.
No paid providers, raw event output, arbitrary model code or external publication.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="blackgrid:phase2")
    parser.add_argument("--host-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    args.output.mkdir(parents=True, exist_ok=True)
    result = {"status": "running", "image": args.image, "paid_calls": False, "usd": 0,
              "checks": {}, "limitations": ["single-host mock workflow; no production load/security certification"]}
    name = "blackgrid-phase2-verify-" + uuid.uuid4().hex[:10]
    volume = name + "-state"
    result.update(container=name, state_volume=volume)

    def save():
        (args.output / "container_acceptance.json").write_text(json.dumps(result, indent=2) + "\n")

    def docker(*argv: str, timeout: float = 60) -> str:
        with (args.output / "container_commands.log").open("a", encoding="utf-8") as log:
            log.write(json.dumps(["docker", *argv]) + "\n")
            log.flush()
            completed = subprocess.run(["docker", *argv], capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=timeout)
            log.write(completed.stdout + completed.stderr + "\n")
        if completed.returncode:
            raise RuntimeError(f"Docker command failed ({argv[0]}, exit {completed.returncode}); inspect local log")
        return completed.stdout.strip()

    def code(source: str) -> str:
        return docker("exec", name, "python", "-c", source)

    def check(label: str, value):
        result["checks"][label] = value
        save()
        print(label, json.dumps(value), flush=True)

    def wait_ready():
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            try:
                reply = json.loads(code("from blackgrid.operations.health import readiness; "
                    "from blackgrid.operations.settings import load_settings; import json; "
                    "print(json.dumps(readiness(load_settings())))"))
                if not reply:
                    return
            except RuntimeError:
                pass
            time.sleep(1)
        raise RuntimeError("service did not become ready within 40 seconds")

    def run_ids() -> list[str]:
        return json.loads(code("import sqlite3,json; c=sqlite3.connect('/app/runs/workflow.sqlite'); "
                               "print(json.dumps([r[0] for r in c.execute('SELECT run_id FROM runs ORDER BY created_utc')]))"))

    def fingerprint(run_id: str) -> dict:
        return json.loads(code("from blackgrid.analysis.parity import fingerprint; from pathlib import Path; "
                               f"import json; print(json.dumps(fingerprint(Path('/app/runs') / {run_id!r})))"))

    # Fixed BEFORE container outcomes: graph/claims/counts/status exact; full numeric
    # output absolute tolerance 1e-12 only if platform floating serialization differs.
    protocol = {"float_absolute_tolerance": 1e-12, "relative_tolerance": 0,
                "exact": ["projection identity", "integer counts", "claims", "flags", "verdict", "budget/call counters"],
                "volatile_keys": ["elapsed_s", "created_utc", "finished_utc", "run_id", "fetched_utc"]}
    (args.output / "parity_protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    save()
    created = False
    try:
        from blackgrid.analysis.parity import fingerprint as host_fingerprint
        reference = host_fingerprint(args.host_run)
        assert reference["status"] == "completed" and reference["actual_usd"] == 0
        result["host_fingerprint"] = reference
        image_check = """import importlib.util,json,os,pathlib
import igraph,leidenalg,networkx,numpy,scipy,sklearn
p=pathlib.Path('/app')
assert os.getuid()==10001
assert all(not (p/x).exists() for x in ['.env','.git','tests','data/CollegeMsg.txt/CollegeMsg.txt','runs/workflow.sqlite','results/sprint06-v2/summary.json'])
assert importlib.util.find_spec('pytest') is None
assert not any(k in os.environ for k in ['OPEN_ROUTER_API_KEY','OPENROUTER_API_KEY'])
print(json.dumps({'uid':os.getuid(),'python':__import__('platform').python_version(),'private_inputs_absent':True,'runtime_imports':True,'pytest_absent':True}))"""
        check("image_boundary", json.loads(docker("run", "--rm", "--network", "none", "--read-only",
            "--tmpfs", "/tmp:size=64m,mode=1777", "--entrypoint", "python", args.image, "-c", image_check)))
        docker("volume", "create", volume)
        docker("run", "-d", "--name", name, "--init", "--network", "none", "--read-only",
               "--memory", "2g", "--cpus", "1", "--pids-limit", "128", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges:true", "--tmpfs", "/tmp:size=64m,mode=1777",
               "--env", "BLACKGRID_SHUTDOWN_GRACE_SECONDS=0.25",
               "--mount", f"type=bind,source={root / 'data'},target=/app/data,readonly",
               "--mount", f"type=volume,source={volume},target=/app/runs", args.image)
        created = True
        wait_ready()
        inspected = json.loads(docker("inspect", name))[0]
        host = inspected["HostConfig"]
        assert host["ReadonlyRootfs"] and host["NetworkMode"] == "none"
        assert host["Memory"] == 2 * 1024**3 and host["NanoCpus"] == 10**9
        assert inspected["Config"]["User"] == "10001:10001"
        assert not host["PortBindings"] and host["CapDrop"] == ["ALL"]
        assert all(not m["RW"] for m in inspected["Mounts"] if m["Destination"] == "/app/data")
        check("runtime_controls", {"non_root": True, "network": "none", "read_only_root": True,
              "memory_bytes": host["Memory"], "nano_cpus": host["NanoCpus"], "pids_limit": host["PidsLimit"]})
        docker("exec", name, "blackgrid", "--help")
        docker("exec", name, "python", "-m", "blackgrid", "run", "/app/configs/collegemsg_sprint01.json",
               "--mode", "mock", "--data-root", "/app", "--runs-dir", "/app/runs", "--no-cache", timeout=600)
        first = run_ids()[-1]
        candidate = fingerprint(first)
        assert candidate == reference, "host/container fingerprint differs; preserve result and investigate before relaxing parity"
        check("clean_offline_exact_parity", candidate)
        docker("stop", "--time", "3", name)
        assert json.loads(docker("inspect", name))[0]["State"]["ExitCode"] == 0
        docker("start", name)
        wait_ready()
        assert fingerprint(first) == candidate
        check("completed_state_survives_restart", True)
        # Start the same existing mock workflow via its real console action route.
        code("""import http.client,json,re
c=http.client.HTTPConnection('127.0.0.1',8765,timeout=3); c.request('GET','/'); page=c.getresponse().read().decode()
boot=json.loads(re.search(r'id="bg-boot">(.*?)</script>',page,re.S).group(1))
c.request('POST','/api/action',json.dumps({'action':'start'}),{'Content-Type':'application/json','X-Blackgrid-Token':boot['token']})
r=c.getresponse(); assert r.status==202; r.read(); c.close()""")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            ids = run_ids()
            if len(ids) > 1:
                current = ids[-1]
                dispatched = code("import sqlite3; c=sqlite3.connect('/app/runs/workflow.sqlite'); "
                    f"print(c.execute(\"SELECT COUNT(*) FROM operations WHERE run_id=? AND kind='tool' AND state='dispatched'\",({current!r},)).fetchone()[0])")
                if int(dispatched):
                    break
            time.sleep(.2)
        else:
            raise RuntimeError("did not observe an in-flight numerical tool before interruption")
        docker("stop", "--time", "3", name)
        stopped = json.loads(docker("inspect", name))[0]["State"]
        assert stopped["ExitCode"] == 2 and not stopped["OOMKilled"]
        check("bounded_interruption", {"exit_code": 2, "oom_killed": False, "run_id": current})
        docker("start", name)
        wait_ready()
        # Force is safe ONLY here: this harness proved the prior process stopped.
        docker("exec", name, "python", "-m", "blackgrid", "resume", current, "--runs-dir", "/app/runs",
               "--cache-dir", "/app/runs/cache", "--force-unlock", timeout=600)
        resumed = fingerprint(current)
        assert resumed == reference, "resumed run differs from the current-source host reference"
        check("interrupted_resume_exact_parity", resumed)
        check("post_resume_readiness", json.loads(code("from blackgrid.operations.health import readiness; "
             "from blackgrid.operations.settings import load_settings; import json; print(json.dumps(readiness(load_settings())))")) == [])
        result["status"] = "passed"
        return 0
    except Exception as exc:
        result.update(status="failed", failure=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        if created:
            try:
                docker("stop", "--time", "3", name)
            except Exception:
                result["cleanup"] = "container stop requires inspection"
        save()
        print("Evidence:", args.output / "container_acceptance.json", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
