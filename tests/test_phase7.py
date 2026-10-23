"""Controlled storage/resource/provider faults and adversarial artifact boundaries."""
import json
import sqlite3
import sys
from contextlib import closing
import pytest
from fastapi.testclient import TestClient
from blackgrid.operations.api import create_app
from blackgrid.operations.api_jobs import Jobs, Submission
from blackgrid.agent import http_transport
from tests.test_api import CREDS,headers
from tests.test_deployment import settings


@pytest.mark.parametrize("status,category",[(429,"transient"),(503,"transient"),(401,"permanent")])
def test_provider_status_is_classified_without_key_or_body_disclosure(monkeypatch,status,category):
    from urllib.error import HTTPError
    class Opener:
        def open(self,*args,**kwargs): raise HTTPError('https://openrouter.ai/api/v1/models',status,'PRIVATE',{},None)
    monkeypatch.setattr(http_transport.urllib.request,"build_opener",lambda *args:Opener())
    reply = http_transport.request(dict(url='https://openrouter.ai/api/v1/models',method='GET',
        timeout_s=1,deny_redirects=True,headers={'Authorization':'Bearer PRIVATE'}))
    assert reply['category'] == category and not reply['ok'] and 'PRIVATE' not in json.dumps(reply)


@pytest.mark.parametrize("body",[b'{',b'PRIVATE'*200000])
def test_provider_malformed_or_oversized_output_remains_uncertain(monkeypatch,body):
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,limit): return body[:limit]
    class Opener:
        def open(self,*args,**kwargs): return Response()
    monkeypatch.setattr(http_transport.urllib.request,"build_opener",lambda *args:Opener())
    reply = http_transport.request(dict(url='https://openrouter.ai/api/v1/chat/completions',method='POST',
        body={},timeout_s=1,deny_redirects=True,headers={}))
    assert reply['category'] == 'uncertain' and not reply['ok'] and 'PRIVATE' not in json.dumps(reply)


def test_actual_sqlite_read_only_failure_rolls_back_admission(settings,monkeypatch):
    monkeypatch.setattr(Jobs,'kick',lambda *args:None)
    jobs = Jobs(settings)
    original = jobs.db
    try:
        dbfile = jobs.root/'jobs.sqlite'
        def read_only(): return sqlite3.connect(dbfile.resolve().as_uri()+'?mode=ro',uri=True)
        monkeypatch.setattr(jobs,'db',read_only)
        with pytest.raises(sqlite3.OperationalError): jobs.submit('alice','readonly',Submission())
        monkeypatch.setattr(jobs,'db',original)
        with closing(jobs.db()) as db: assert db.execute('select count(*) from jobs').fetchone()[0] == 0
    finally: jobs.close()


@pytest.mark.skipif(sys.platform != 'linux',reason='Linux resource limit and exit classification')
def test_memory_exhausted_child_is_terminal_and_not_blindly_retried(settings,monkeypatch):
    import subprocess
    original = subprocess.Popen
    children = []
    def exhausted(argv,**kwargs):
        code = "import resource; resource.setrlimit(resource.RLIMIT_AS,(64*1024**2,64*1024**2)); x=bytearray(256*1024**2)"
        child = original([sys.executable,'-c',code],**kwargs)
        children.append(child)
        return child
    monkeypatch.setattr('blackgrid.operations.api_jobs.subprocess.Popen',exhausted)
    jobs = Jobs(settings)
    try:
        reply,_ = jobs.submit('alice','memory-fault',Submission())
        jobs.worker.join(15)
        row = jobs.row('alice',reply['job_id'])
        assert row['state'] == 'failed' and row['error_code'] == 'execution_failed'
        assert row['attempts'] == len(children) == 1 and children[0].poll() is not None
        assert row['finished'] and row['charged_usd'] == 0
    finally: jobs.close()


@pytest.mark.skipif(sys.platform != 'linux',reason='genuine contained worker')
def test_partial_artifact_returns_stable_unavailable_and_cross_owner_stays_denied(settings):
    with TestClient(create_app(settings,CREDS),base_url='http://127.0.0.1') as client:
        job = client.post('/api/v1/jobs',json={'question':'Which nodes have the highest degree?'},headers=headers()).json()['job_id']
        jobs = client.app.state.jobs
        jobs.worker.join(40)
        assert jobs.row('alice',job)['state'] == 'completed'
        run = jobs.run_folder('alice',job)
        path = run/'graph_record.json'
        saved = path.read_bytes()
        path.write_bytes(b'{"PRIVATE_PARTIAL":')
        try:
            reply = client.get(f'/api/v1/jobs/{job}/results',headers=headers())
            assert reply.status_code == 409 and reply.json()['error']['code'] == 'results_unavailable'
            assert 'PRIVATE' not in reply.text
            assert client.get(f'/api/v1/jobs/{job}/results',headers=headers('bob')).status_code == 404
        finally: path.write_bytes(saved)
        assert client.get(f'/api/v1/jobs/{job}/results',headers=headers()).status_code == 200
