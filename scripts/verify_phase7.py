"""Contained synthetic restore/restart drill; runs only inside the Linux test image."""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from fastapi.testclient import TestClient
from blackgrid.operations.api import create_app
from blackgrid.operations.api_jobs import Jobs,Submission
from blackgrid.operations.backup import create,restore,verify
from blackgrid.operations.settings import Settings
from scripts.generate_phase6 import generate
from tests.test_api import CREDS,headers


def main():
    assert os.name == 'posix' and Path('/evidence').is_dir()
    assert not os.environ.get('BLACKGRID_API_LIVE_POLICY_FILE')
    root = Path('/tmp/phase7-restore-drill')
    root.mkdir()
    generated = root/'fixtures'
    generate(generated,sizes=(100,))
    state = root/'state'
    (state/'cache').mkdir(parents=True)
    settings = Settings(environment='test',config=generated/'public/stochastic_block-100.json',
        data_root=generated/'public',runs_dir=state)
    jobs = Jobs(settings)
    try:
        reply,_ = jobs.submit('alice','phase7-fixed',Submission(question='Is community structure stronger than expected from node degrees?'))
        job = reply['job_id']
        jobs.worker.join(60)
        assert not jobs.worker.is_alive()
        before = jobs.results('alice',job)
        assert before['summary']['actual_usd'] == 0
        original = jobs.row('alice',job)
        assert original['state'] == 'completed' and original['attempts'] == 1
    finally: jobs.close()
    snapshot = root/'snapshot'
    backed = create(state,snapshot)
    manifest = verify(snapshot)
    state.rename(root/'retained-original')  # Simulate lost state without deleting evidence.
    started = time.monotonic()
    restored = restore(snapshot,state)
    restore_seconds = time.monotonic()-started
    # Every artifact/database byte in the restored tree is independently checked.
    for name,item in manifest['files'].items():
        assert hashlib.sha256((state/name).read_bytes()).hexdigest() == item['sha256']
    restart_started = time.monotonic()
    with TestClient(create_app(settings,CREDS),base_url='http://127.0.0.1') as client:
        assert client.get('/health/ready').status_code == 200
        assert client.get(f'/api/v1/jobs/{job}/results',headers=headers()).json() == before
        assert client.get(f'/api/v1/jobs/{job}/results',headers=headers('bob')).status_code == 404
        replay = client.post('/api/v1/jobs',json={'question':'Is community structure stronger than expected from node degrees?'},headers=headers()|{'Idempotency-Key':'phase7-fixed'})
        assert replay.status_code == 200 and replay.json()['job_id'] == job
        assert client.app.state.jobs.row('alice',job) == original
        with closing(client.app.state.jobs.db()) as db:
            assert db.execute('select count(*) from jobs').fetchone()[0] == 1
    restarted_seconds = time.monotonic()-restart_started
    report = dict(version='production-phase7-v1',mode='mock',origin='synthetic',real_provider_calls=0,
        actual_usd=0,backup=backed,restore=restored,restore_seconds=restore_seconds,
        restored_api_check_seconds=restarted_seconds,files_exact=len(manifest['files']),
        all_job_columns_exact=True,scientific_api_result_exact=True,owner_denied=True,
        idempotent_replay_exact=True,duplicate_jobs=0,lost_jobs=0,corrupted_artifacts=0,
        workflow_attempts=1,production_state_touched=False,
        limitations=['single synthetic completed-job drill','same absolute state path retained',
                    'not a power-loss or physical-disk disaster simulation','no real-provider recovery claim'])
    Path('/evidence/restore_drill.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__': main()
