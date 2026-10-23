"""Gated idle-only promotion on the existing local host; never public/cloud deployment."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from release_gate import evidence, require
from monitor_api import connection

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/production_phase9'


def command(argv):
    return subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=True, timeout=240).stdout


def ready(request):
    deadline = time.monotonic()+90
    while time.monotonic() < deadline:
        try:
            if request('/health/ready')['status'] == 'ready': return
        except (OSError, RuntimeError): pass
        time.sleep(2)
    raise RuntimeError('readiness deadline')


def rows():
    code = """import sqlite3,json,hashlib
c=sqlite3.connect('file:/app/runs/api/jobs.sqlite?mode=ro',uri=True)
c.row_factory=sqlite3.Row
data=[dict(r) for r in c.execute('select * from jobs order by id')]
assert not any(r['state'] in ('queued','running') for r in data)
print(json.dumps(dict(jobs=len(data),sha256=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),charged_usd=sum(r['charged_usd'] for r in data))))
"""
    return json.loads(command(['docker','exec','blackgrid-blackgrid-1','python','-c',code]))


def main():
    manifest = json.loads((OUT/'evidence/release_manifest.json').read_bytes())
    image_id = json.loads(command(['docker','image','inspect','blackgrid:phase9']))[0]['Id']
    require(image_id == manifest['image_id'], 'Candidate image changed after assessment')
    for name, digest in (manifest['source_hashes'] | manifest['verification_hashes']).items():
        require(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, 'Release source changed')
    assessment = evidence(OUT, image_id, 'local-restricted', now=time.time())
    attempts = list((OUT/'benchmark').glob('*/reconciliation.json'))
    require(len(attempts) == 1, 'Exactly one reconciled final benchmark is required')
    load = json.loads(attempts[0].read_bytes())
    require(load['reconciled'] and load['actual_usd'] == 0 and load['image_id'] == image_id,
            'Load verification does not match release image')
    require(all(s['incomplete'] == s['censored'] == s['unexpected_errors'] == 0 for s in load['stages']),
            'Final workload contains unsuccessful jobs or unexpected HTTP errors')
    config = json.loads(command(['docker','compose','config','--format','json']))
    service = config['services']['blackgrid']
    require(service['image'] == 'blackgrid:phase9' and service['read_only'] and service['user'] == '10001:10001',
            'Unexpected deployment configuration')
    for mount in service['volumes']:
        if mount['type'] == 'bind':
            require(mount['read_only'] and Path(mount['source']).exists(), 'Invalid read-only binding')
    before = rows()
    previous_image = json.loads(command(['docker','inspect','blackgrid-blackgrid-1']))[0]['Image']
    (OUT/'evidence/promotion_preflight.json').write_text(json.dumps(dict(
        assessment=assessment, prior_image_id=previous_image, candidate_image_id=image_id,
        prior_state=before, scope='local-restricted', configuration_valid=True), indent=2), encoding='utf-8')
    # The existing deployment procedure checks idle state again and makes an offline private snapshot.
    subprocess.run([sys.executable, str(ROOT/'scripts/deploy_phase9.py')], cwd=ROOT, check=True, timeout=1200)
    request = connection()
    ready(request)
    deployed = rows()
    original_result = json.loads((OUT/'evidence/parity_result.json').read_bytes())
    job = original_result['job_id']
    override = ROOT/'tmp/phase9-rollback.yml'
    override.write_text('services:\n  blackgrid:\n    image: '+previous_image+'\n', encoding='utf-8')
    started = time.monotonic()
    try:
        command(['docker','compose','-f','docker-compose.yml','-f',str(override),'up','-d','--no-build'])
        ready(request)
        require(rows() == deployed, 'Rollback changed authoritative job/billing state')
        require(request(f'/api/v1/jobs/{job}/results') == original_result, 'Rollback result mismatch')
        rolled_id = json.loads(command(['docker','inspect','blackgrid-blackgrid-1']))[0]['Image']
        require(rolled_id == previous_image, 'Rollback did not select the prior immutable image')
    finally:
        command(['docker','compose','up','-d','--no-build'])
        ready(request)
    require(rows() == deployed, 'Return to release changed authoritative job/billing state')
    require(request(f'/api/v1/jobs/{job}/results') == original_result, 'Release result mismatch')
    report = dict(scope='local-restricted', previous_image_id=previous_image, image_id=image_id,
        rollback_and_return_seconds=time.monotonic()-started, state_before_rollback=deployed,
        all_job_columns_and_spend_exact=True, aggregate_result_exact=True,
        database_migration='none; unchanged additive initialization', restored_old_ledger=False,
        final_readiness=True, new_provider_usd=0, real_provider_calls=0)
    (OUT/'evidence/rollback.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
