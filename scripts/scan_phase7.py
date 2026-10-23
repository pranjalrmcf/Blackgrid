"""Scan a local runtime archive with the official scanner; no image upload/socket."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = 'aquasec/trivy:0.76.0'


def command(args,timeout=1200):
    return subprocess.run(args,cwd=ROOT,text=True,capture_output=True,check=True,timeout=timeout).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',default='blackgrid:phase7')
    args = parser.parse_args()
    if args.image != 'blackgrid:phase7': parser.error('this registered check targets blackgrid:phase7')
    output = ROOT/'docs/production_phase7/evidence'
    private = ROOT/'tmp/phase7-scan'
    private.mkdir(exist_ok=True)
    archive = private/'runtime.tar'
    started = time.monotonic()
    info = json.loads(command(['docker','image','inspect',args.image]))[0]
    scanner = json.loads(command(['docker','image','inspect',SCANNER]))[0]
    scanner_digest = scanner['RepoDigests'][0]
    command(['docker','image','save','-o',str(archive),args.image])
    flags = ['docker','run','--rm','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--memory','2g','--cpus','1','--pids-limit','128','--tmpfs','/tmp:size=768m,mode=1777',
        '--mount',f'type=bind,source={archive},target=/input/runtime.tar,readonly',
        '--mount',f'type=bind,source={output},target=/evidence',
        '--mount','type=volume,source=blackgrid-trivy-cache,target=/cache']
    argv = flags+[scanner_digest,'image','--cache-dir','/cache','--scanners','vuln','--pkg-types','os,library',
        '--list-all-pkgs','--format','json','--output','/evidence/scan_phase7.json','--input','/input/runtime.tar',
        '--timeout','10m','--quiet']
    result = subprocess.run(argv,cwd=ROOT,text=True,capture_output=True,timeout=660)
    (output/'scan_phase7.log').write_text(result.stderr,encoding='utf-8')
    result.check_returncode()
    version = json.loads(command(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL',
        '--mount','type=volume,source=blackgrid-trivy-cache,target=/root/.cache/trivy,readonly',
        scanner_digest,'version','--format','json']))
    scan = json.loads((output/'scan_phase7.json').read_bytes())
    findings = [v for target in scan['Results'] for v in target.get('Vulnerabilities',[])]
    report = dict(image=args.image,image_id=info['Id'],scanner_digest=scanner_digest,
        scanner=version,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        scan_sha256=hashlib.sha256((output/'scan_phase7.json').read_bytes()).hexdigest(),
        seconds=time.monotonic()-started,severity_counts=dict(Counter(v['Severity'] for v in findings)),
        coverage=[dict(target=t['Target'],type=t['Type'],packages=len(t.get('Packages',[])),findings=len(t.get('Vulnerabilities',[]))) for t in scan['Results']],
        fixed_version_available=sum(bool(v.get('FixedVersion')) for v in findings),
        image_uploaded=False,docker_socket_mounted=False,private_state_or_credentials_mounted=False)
    (output/'scan_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 2 if report['severity_counts'].get('CRITICAL',0) else 0


if __name__ == '__main__': raise SystemExit(main())
