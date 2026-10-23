"""Verify cumulative deployment, exact mock parity and retained state; never paid."""
from __future__ import annotations
import hashlib
import json
import subprocess
import time
import uuid
from datetime import datetime
from monitor_api import ROOT, connection

OUTPUT = ROOT/"docs/production_phase6/evidence"


def docker(*args, code=None):
    return subprocess.run(["docker", *args], input=code, text=True, capture_output=True, check=True).stdout


def main(*, initial_stopped=False, repeat_warm=False):
    request = connection()
    if not initial_stopped:
        snapshot = request("/api/v1/monitoring.json")
        assert snapshot["scheduler_available"]
    # A deployment/restart must not interrupt somebody else's work.
    code = """import sqlite3,json
c=sqlite3.connect('/app/runs/api/jobs.sqlite')
print(c.execute("select count(*) from jobs where state in ('running','queued')").fetchone()[0])
"""
    if not initial_stopped:
        assert int(docker("exec", "-i", "blackgrid-blackgrid-1", "python", "-", code=code)) == 0, "Service has active jobs"
    docker("compose", "up", "-d", "--no-build")
    def ready():
        deadline = time.monotonic()+90
        while time.monotonic() < deadline:
            try:
                if request("/health/ready")["status"] == "ready": return
            except (OSError, RuntimeError): pass
            time.sleep(2)
        raise RuntimeError("readiness deadline")
    ready()
    sources = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((ROOT/"src").rglob("*")) if p.is_file() and p.suffix in (".py", ".html", ".css", ".js")}
    code = """import os,json,hashlib,pathlib,importlib.util
root=pathlib.Path('/app')
sources={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'src').rglob('*')) if p.is_file() and p.suffix in ('.py','.html','.css','.js')}
print(json.dumps({'uid':os.getuid(),'sources':sources,'excluded':{n:importlib.util.find_spec(n) is None for n in ('locust','pytest','vllm')}}))
"""
    running = json.loads(docker("exec", "-i", "blackgrid-blackgrid-1", "python", "-", code=code))
    assert running["uid"] == 10001 and running["sources"] == sources
    assert all(running["excluded"].values())
    info = json.loads(docker("inspect", "blackgrid-blackgrid-1"))[0]
    limits = info["HostConfig"]
    assert limits["ReadonlyRootfs"] and limits["Memory"] == 2*1024**3
    assert limits["NanoCpus"] == 10**9 and limits["PidsLimit"] == 128
    assert limits["CapDrop"] == ["ALL"] and "no-new-privileges:true" in limits["SecurityOpt"]
    assert limits["LogConfig"] == {"Type":"json-file", "Config":{"max-file":"3", "max-size":"10m"}}
    assert info["NetworkSettings"]["Ports"]["8765/tcp"] == [{"HostIp":"127.0.0.1", "HostPort":"8765"}]
    volumes = [m for m in info["Mounts"] if m["Type"] == "volume"]
    assert len(volumes) == 1 and volumes[0]["Name"] == "blackgrid_blackgrid-state"
    assert all(not m["RW"] for m in info["Mounts"] if m["Type"] == "bind")
    baseline = json.loads((ROOT/"docs/production_phase5/baseline.json").read_bytes())
    job = request("/api/v1/jobs", {"mode":"mock", "question":"Does this network show stronger community structure than expected from node degrees?"}, "phase6-"+uuid.uuid4().hex)["job_id"]
    start = time.monotonic()
    while time.monotonic()-start < 960:
        row = request(f"/api/v1/jobs/{job}")
        if row["state"] not in ("queued", "running"): break
        time.sleep(2)
    assert row["state"] == "completed"
    cold_wall = time.monotonic()-start
    cold_terminal = (datetime.fromisoformat(row['completed_utc'])-datetime.fromisoformat(row['created_utc'])).total_seconds()
    result = request(f"/api/v1/jobs/{job}/results")
    assert {k:v for k,v in result.items() if k != "job_id"} == baseline["result"]
    trace = request(f"/api/v1/jobs/{job}/trace")
    assert trace["available"] and not trace["open_span_ids"]
    docker("compose", "restart", "blackgrid")
    ready()
    assert request(f"/api/v1/jobs/{job}/results") == result
    assert request(f"/api/v1/jobs/{job}/trace")["spans"][:len(trace["spans"])] == trace["spans"]
    warm_evidence = {}
    if repeat_warm:
        warm_start = time.monotonic()
        warm_job = request("/api/v1/jobs", {"mode":"mock", "question":"Does this network show stronger community structure than expected from node degrees?"}, "warm-"+uuid.uuid4().hex)["job_id"]
        while time.monotonic()-warm_start < 120:
            warm_row = request(f"/api/v1/jobs/{warm_job}")
            if warm_row["state"] not in ("queued","running"): break
            time.sleep(.5)
        assert warm_row["state"] == "completed"
        warm_result = request(f"/api/v1/jobs/{warm_job}/results")
        assert {k:v for k,v in warm_result.items() if k != "job_id"} == baseline["result"]
        hits = sum(t.get('cached',False) for t in warm_row['progress']['tools'])
        assert hits == 3 and warm_row['progress']['llm_calls'] == 1
        warm_evidence = dict(cold_job_wall_seconds=cold_wall,warm_job_wall_seconds=time.monotonic()-warm_start,
            cold_creation_to_terminal_seconds=cold_terminal,
            warm_creation_to_terminal_seconds=(datetime.fromisoformat(warm_row['completed_utc'])-datetime.fromisoformat(warm_row['created_utc'])).total_seconds(),
            warm_job_id=warm_job,warm_cache_hits=hits,cache_survives_restart=True,llm_call_counters_exact=True)
        (OUTPUT/'warm_parity_result.json').write_text(json.dumps(warm_result,indent=2),encoding='utf-8')
    catalog = request("/api/v1/capabilities")
    assert len(catalog["tools"]) == 18 and all(t["available"] for t in catalog["tools"])
    # Compare all columns of the original durable records; never restore an old ledger.
    backup = json.loads((OUTPUT/"pre_deploy.json").read_bytes())
    code = """import sqlite3,json,hashlib
old=sqlite3.connect('file:/app/runs/api/"""+backup["backup"]+"""?mode=ro',uri=True)
new=sqlite3.connect('file:/app/runs/api/jobs.sqlite?mode=ro',uri=True)
old.row_factory=new.row_factory=sqlite3.Row
before=[dict(r) for r in old.execute('select * from jobs order by id')]
for row in before:
    assert dict(new.execute('select * from jobs where id=?',(row['id'],)).fetchone()) == row
paid=new.execute('select sum(charged_usd) from jobs').fetchone()[0]
print(json.dumps({'original_rows_exact':len(before),'api_charged_usd':paid}))
"""
    ledger = json.loads(docker("exec", "-i", "blackgrid-blackgrid-1", "python", "-", code=code))
    assert ledger["original_rows_exact"] == backup["original_jobs"]
    assert ledger["api_charged_usd"] == backup["api_charged_usd"]
    evidence = dict(image=info["Config"]["Image"], image_id=info["Image"], uid=10001,
        source_and_assets_exact=True, source_files=len(sources), excluded_runtime_packages=running["excluded"],
        memory_bytes=limits["Memory"], nano_cpus=limits["NanoCpus"], pids_limit=limits["PidsLimit"],
        read_only_root=True, all_binds_read_only=True, capabilities_dropped=True, localhost_only=True,
        log_rotation=limits["LogConfig"], persistent_volume=volumes[0]["Name"], job_id=job,
        exact_api_result_parity=True, restart_result_exact=True, restart_trace_prefix_exact=True,
        registered_tools_available=18, paid_calls=0, new_mock_jobs=2 if repeat_warm else 1, **ledger, **warm_evidence)
    (OUTPUT/"source_manifest.json").write_text(json.dumps(sources,indent=2),encoding="utf-8")
    (OUTPUT/"deployment_verification.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    (OUTPUT/"parity_result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(evidence,indent=2))


if __name__ == "__main__": main()
