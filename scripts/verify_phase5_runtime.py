"""Verify source/image/resource parity without exporting secrets or raw inputs."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def docker(*args, code=None):
    result = subprocess.run(["docker", *args], input=code, text=True, capture_output=True, check=True)
    return result.stdout


def main():
    source = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT/"src").rglob("*.py"))}
    code = """import os,json,hashlib,pathlib
root=pathlib.Path('/app')
sources={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'src').rglob('*.py'))}
print(json.dumps({'uid':os.getuid(),'sources':sources}))
"""
    running = json.loads(docker("exec", "-i", "blackgrid-blackgrid-1", "python", "-", code=code))
    assert running["sources"] == source and running["uid"] == 10001
    info = json.loads(docker("inspect", "blackgrid-blackgrid-1"))[0]
    limits = info["HostConfig"]
    assert limits["ReadonlyRootfs"] and limits["Memory"] == 2*1024**3
    assert limits["NanoCpus"] == 10**9 and limits["PidsLimit"] == 128
    assert limits["LogConfig"] == {"Type": "json-file", "Config": {"max-file": "3", "max-size": "10m"}}
    assert limits["CapDrop"] == ["ALL"] and "no-new-privileges:true" in limits["SecurityOpt"]
    assert info["NetworkSettings"]["Ports"]["8765/tcp"] == [{"HostIp": "127.0.0.1", "HostPort": "8765"}]
    volumes = [m for m in info["Mounts"] if m["Type"] == "volume"]
    assert len(volumes) == 1 and volumes[0]["Name"] == "blackgrid_blackgrid-state"
    assert all(not m["RW"] for m in info["Mounts"] if m["Type"] == "bind")
    evidence = dict(image=info["Config"]["Image"], image_id=info["Image"], uid=running["uid"],
        source_files=len(source), source_exact=True, read_only_root=True, memory_bytes=limits["Memory"],
        nano_cpus=limits["NanoCpus"], pids_limit=limits["PidsLimit"],
        log_rotation=limits["LogConfig"], persistent_volume=volumes[0]["Name"],
        all_input_and_secret_binds_read_only=True, localhost_only=True)
    output = ROOT/"docs"/"production_phase5"
    for relative in ("Dockerfile", "docker-compose.yml", "pyproject.toml", "uv.lock", "tests/test_monitoring.py",
                     "scripts/monitor_api.py", "scripts/set_api_operator.py", "scripts/verify_phase5.py", "scripts/verify_phase5_runtime.py",
                     "scripts/verify_phase5_restart.py"):
        source[relative] = hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
    (output/"source_manifest.json").write_text(json.dumps(source, indent=2, sort_keys=True), encoding="utf-8")
    (output/"runtime_verification.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
