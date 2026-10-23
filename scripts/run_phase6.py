"""One-command isolated, offline Phase 6 pilot; no production submissions or vLLM."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import secrets
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from generate_phase6 import generate

ROOT = Path(__file__).resolve().parents[1]


def command(args, *, env=None, timeout=300, log=None, check=True):
    if log:
        with Path(log).open("w", encoding="utf-8") as output:
            return subprocess.run(args, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
                                  text=True, timeout=timeout, check=check)
    return subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout, check=check)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--image", default="blackgrid:phase6")
    parser.add_argument("--benchmark-image", default="blackgrid:phase6-benchmark")
    parser.add_argument("--reports", type=Path, default=ROOT/"results/production_phase6")
    parser.add_argument("--tool-cache", action="store_true")
    args = parser.parse_args()
    protocol_path = ROOT/"protocols/production_phase6_v2.json"
    protocol = json.loads(protocol_path.read_bytes())
    inputs = ROOT/"tmp/phase6-inputs-v1"
    if not inputs.exists():
        generate(inputs, sizes=tuple(protocol["generate_nodes"]), seed=protocol["seed"])
    else:
        manifests = json.loads((inputs/"manifest.json").read_text())
        expected = hashlib.sha256((ROOT/"scripts/generate_phase6.py").read_bytes()).hexdigest()
        if len(manifests) != 15 or any(m["generator_sha256"] != expected for m in manifests):
            raise ValueError("existing generator identity changed; preserve inputs and version a new protocol")
    if args.prepare_only:
        print("15 synthetic inputs prepared. Truth is outside the runtime input directory.")
        return 0
    reports = args.reports.resolve()
    reports.mkdir(parents=True, exist_ok=True)
    if len([p for p in reports.iterdir() if p.is_dir()]) >= 20:
        raise ValueError("retained attempt limit reached")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")+"-"+secrets.token_hex(3)
    output = reports/stamp
    output.mkdir()
    started = time.monotonic()
    manifest = dict(version=protocol["version"], attempt=stamp, mode="mock", origin="synthetic",
        protocol_sha256=hashlib.sha256(protocol_path.read_bytes()).hexdigest(), state="preparing",
        vllm="out_of_scope", stages=[], actual_usd=0, real_provider_calls=0)
    (output/"registered_protocol.json").write_bytes(protocol_path.read_bytes())
    (output/"attempt.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    private = ROOT/".secrets/phase6"/stamp
    private.mkdir(parents=True, mode=0o700)
    tokens = [{"subject":"bench-observer", "token":secrets.token_urlsafe(32)}]+[
        {"subject":f"bench-{i:02d}", "token":secrets.token_urlsafe(32)} for i in range(10)]
    registry = {"clients":[{"subject":p["subject"], "token_sha256":hashlib.sha256(p["token"].encode()).hexdigest(),
                            "operator":i==0} for i,p in enumerate(tokens)]}
    for name, data in (("clients.json",registry),("benchmark-tokens.json",tokens)):
        fd = os.open(private/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as stream: json.dump(data,stream)
    volume = "blackgrid-phase6-"+stamp.lower()
    env = os.environ.copy()
    env.update(BLACKGRID_BENCHMARK_INPUTS=str(inputs/"public"),
               BLACKGRID_BENCHMARK_CREDENTIALS=str(private/"clients.json"), BLACKGRID_BENCHMARK_VOLUME=volume,
               BLACKGRID_BENCHMARK_IMAGE=args.image, BLACKGRID_BENCHMARK_TOOL_CACHE=str(args.tool_cache).lower())
    compose = ["docker","compose","-f","docker-compose.benchmark.yml"]
    existing = command(["docker","inspect","blackgrid-benchmark-target"],check=False)
    if existing.returncode == 0 and json.loads(existing.stdout)[0]["State"]["Running"]:
        raise ValueError("a benchmark target is already running; preserve and inspect it before another attempt")
    manifest["volume"] = volume
    try:
        for target, image in (("production",args.image),("benchmark",args.benchmark_image)):
            if command(["docker","image","inspect",image],check=False).returncode:
                command(["docker","build","--progress=plain","--target",target,"-t",image,"."], timeout=600,
                        log=output/(target+"_build.log"))
        command(["docker","volume","create",volume])
        command(compose+["up","-d","--no-build"],env=env)
        for _ in range(30):
            health = command(["docker","exec","blackgrid-benchmark-target","python","-m","blackgrid.operations","health","--readiness"],check=False)
            if health.returncode == 0: break
            time.sleep(2)
        else: raise RuntimeError("isolated benchmark target not ready")
        inspected = json.loads(command(["docker","inspect","blackgrid-benchmark-target"]).stdout)[0]
        assert inspected["HostConfig"]["Memory"] == protocol["target_memory_bytes"]
        assert inspected["HostConfig"]["NanoCpus"] == 10**9 and inspected["HostConfig"]["ReadonlyRootfs"]
        binds = [m for m in inspected["Mounts"] if m["Type"]=="bind"]
        assert all(not m["RW"] for m in binds)
        assert not any("truth" in m["Source"] or "openrouter" in m["Source"] or m["Destination"]=="/app/data" for m in binds)
        assert not any("LIVE_POLICY" in e or e.startswith("OPEN_ROUTER_API_KEY=") for e in inspected["Config"]["Env"])
        manifest["target_image_id"] = inspected["Image"]
        manifest["host"] = json.loads(command(["docker","info","--format",'{{json .}}']).stdout)
        manifest["host"] = {k:manifest["host"].get(k) for k in ("NCPU","MemTotal","OSType","Architecture","KernelVersion","ServerVersion")}
        manifest["source_revision"] = command(["git","rev-parse","HEAD"]).stdout.strip()
        manifest["source_dirty"] = bool(command(["git","status","--porcelain"]).stdout)
        source_files = list((ROOT/"src").rglob("*.py"))+list((ROOT/"benchmarks/production").glob("*.py"))
        source_files += [ROOT/p for p in ("Dockerfile","docker-compose.benchmark.yml","protocols/production_phase6_v2.json",
            "scripts/generate_phase6.py","scripts/run_phase6.py","pyproject.toml","uv.lock")]
        manifest["source_hashes"] = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
        manifest["state"] = "running"
        for category, users in [("tools",1)]+[(c,u) for c in ("api","mixed") for u in protocol["api_users"]]:
            if time.monotonic()-started >= protocol["max_total_seconds"]:
                manifest["state"],manifest["stop_reason"] = "stopped","total_deadline"
                break
            name = f"{category}-u{users}"
            (reports/"status.json").write_text(json.dumps(dict(version=protocol["version"],state="running",
                run_id=stamp+"-"+name, category=category,users=0,elapsed_s=0,counts={},series=[])),encoding="utf-8")
            generator = "blackgrid-generator-"+secrets.token_hex(4)
            args_docker = ["docker","run","--rm","--name",generator,"--network","container:blackgrid-benchmark-target",
                "--read-only","--cap-drop","ALL","--security-opt","no-new-privileges","--memory","512m",
                "--cpus","0.5","--pids-limit","128","--tmpfs","/tmp:size=64m,mode=1777",
                "--env","OPENBLAS_NUM_THREADS=1","--env","OMP_NUM_THREADS=1","--env","MKL_NUM_THREADS=1",
                "--mount",f"type=bind,source={reports},target=/evidence",
                "--mount",f"type=bind,source={inputs/'public'},target=/bench/public,readonly",
                "--mount",f"type=bind,source={private/'benchmark-tokens.json'},target=/run/secrets/benchmark-tokens.json,readonly",
                "--mount",f"type=bind,source={ROOT/'.secrets/server-cert.pem'},target=/run/secrets/server-cert.pem,readonly",
                args.benchmark_image,"--category",category,"--users",str(users),"--output",f"/evidence/{stamp}/{name}"]
            print(f"Benchmark {category}: {users} virtual users (offline synthetic)",flush=True)
            try:
                result = command(args_docker, timeout=protocol["stage_deadline_seconds"]+30, log=output/(name+".log"), check=False)
            except subprocess.TimeoutExpired:
                command(["docker","stop","--time","5",generator],timeout=15,check=False)
                manifest["state"],manifest["stop_reason"] = "stopped","generator_deadline"
                break
            manifest["stages"].append({"category":category,"users":users,"exit_code":result.returncode,"directory":name})
            (output/"attempt.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
            if result.returncode:
                manifest["state"],manifest["stop_reason"] = "stopped","stage_failure_or_registered_stop"
                break
        else:
            manifest["state"] = "completed"
    except Exception as error:
        manifest["state"],manifest["stop_reason"] = "failed","orchestration_failure"
        if isinstance(error, subprocess.CalledProcessError):
            (output/"orchestration_error.txt").write_text(error.stderr or "Command failed; inspect retained container state.",encoding="utf-8")
        raise
    finally:
        command(["docker","logs","blackgrid-benchmark-target"],log=output/"target.log",check=False)
        export = """import sqlite3,json
c=sqlite3.connect('/app/runs/api/jobs.sqlite')
c.row_factory=sqlite3.Row
print(json.dumps([dict(r) for r in c.execute('select id,state,created,started,finished,mode,attempts,charged_usd from jobs order by created')]))
"""
        command(["docker","exec","-i","blackgrid-benchmark-target","python","-c",export],log=output/"job_ledger.json",check=False)
        command(compose+["stop"],env=env,timeout=60,check=False)
        manifest["elapsed_s"] = time.monotonic()-started
        (output/"attempt.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print("Evidence:",output,flush=True)
    return 0 if manifest["state"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
