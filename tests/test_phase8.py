"""Cache isolation/invalidation, bounded retention, fail-open recomputation and parity."""
import json
import os
import sys
import time
import pytest
from fastapi.testclient import TestClient
from blackgrid.agent.tools import execute,_cache_key,ProfileArgs
from blackgrid.operations.tool_cache import directory,prune,MAX_AGE_SECONDS
from blackgrid.operations.api import create_app
from scripts.generate_phase6 import generate
from tests.test_api import CREDS,headers
from tests.test_deployment import settings
from tests.test_tools import ctx
from tests.test_api_live import policy


def test_owner_mode_config_and_code_namespaces_cannot_reuse_each_other(tmp_path):
    root=tmp_path/'cache'
    first=directory(root,'alice','mock','config','code')
    (first/'valid.json').write_text('{}')
    assert directory(root,'alice','mock','config','code') == first
    for values in [('bob','mock','config','code'),('alice','live','config','code'),
                   ('alice','mock','new-config','code'),('alice','mock','config','new-code')]:
        changed=directory(root,*values)
        assert changed != first and not (changed/'valid.json').exists()


def test_retention_bounds_include_quarantine_temporary_and_old_files(tmp_path):
    root=tmp_path/'cache'
    root.mkdir()
    for i in range(5):
        path=root/f'{i}.json.rejected'
        path.write_bytes(b'x'*10)
        os.utime(path,(100+i,100+i))
    prune(root,now=110,max_entries=3,max_bytes=20)
    assert {p.name for p in root.iterdir()} == {'3.json.rejected','4.json.rejected'}
    prune(root,now=MAX_AGE_SECONDS+200)
    assert not list(root.iterdir())


def test_unwritable_cache_does_not_fail_a_valid_analysis(ctx,tmp_path):
    blocked=tmp_path/'not-a-directory'
    blocked.write_text('retained')
    ctx.cache_dir=blocked
    result=execute({'tool':'profile_graph','args':{}},ctx)
    assert result.output['nodes'] == len(ctx.graph)
    assert not ctx.calls[-1].cached and ctx.calls[-1].cache_rejected == 'cache_write_unavailable'
    assert blocked.read_text() == 'retained'


def test_oversized_cache_is_rejected_and_graph_is_recomputed(ctx):
    execute({'tool':'profile_graph','args':{}},ctx)
    key=_cache_key('profile_graph',ProfileArgs(),ctx)
    path=ctx.cache_dir/(key+'.json')
    path.write_bytes(b' '*(8*1024**2+1))
    result=execute({'tool':'profile_graph','args':{}},ctx)
    assert result.output['nodes'] == len(ctx.graph) and not ctx.calls[-1].cached
    assert 'byte limit' in ctx.calls[-1].cache_rejected
    assert list(ctx.cache_dir.glob('*.rejected-*'))


@pytest.mark.skipif(sys.platform!='linux',reason='actual contained API worker')
def test_api_repeated_jobs_reuse_only_verified_owner_scoped_tools(settings,tmp_path):
    generate(tmp_path/'input',sizes=(100,))
    configured=settings.model_copy(update={'environment':'test','api_tool_cache':True,
        'config':tmp_path/'input/public/stochastic_block-100.json','data_root':tmp_path/'input/public'})
    expected=None
    with TestClient(create_app(configured,CREDS),base_url='http://127.0.0.1') as client:
        for ordinal,(owner,warm) in enumerate([('alice',False),('alice',True),('bob',False)]):
            auth=headers(owner)|{'Idempotency-Key':f'cache-{ordinal}'}
            job=client.post('/api/v1/jobs',json={'question':'Is community structure stronger than expected from node degrees?'},headers=auth).json()['job_id']
            client.app.state.jobs.worker.join(40)
            assert not client.app.state.jobs.worker.is_alive()
            row=client.get(f'/api/v1/jobs/{job}',headers=auth).json()
            assert row['state']=='completed',row
            tools=row['progress']['tools']
            assert len(tools)==3 and all(t['cached'] is warm for t in tools)
            result=client.get(f'/api/v1/jobs/{job}/results',headers=auth).json()
            result.pop('job_id')
            if expected is None: expected=result
            assert result==expected and result['summary']['llm_calls']==1 and result['summary']['actual_usd']==0
            assert client.get(f'/api/v1/jobs/{job}',headers=headers('bob' if owner=='alice' else 'alice')).status_code==404


@pytest.mark.skipif(sys.platform!='linux',reason='fake-provider broker and contained live worker')
def test_live_cache_never_skips_provider_calls_or_paid_accounting(settings,policy,monkeypatch):
    import hashlib
    import networkx as nx
    from blackgrid.operations import live
    from contextlib import closing
    events=settings.data_root/'events.txt'
    events.write_text(''.join(f'{a} {b} {100+i}\n' for i,(a,b) in enumerate(nx.karate_club_graph().edges())))
    for path in (settings.config,policy.config):
        raw=json.loads(path.read_bytes())
        raw['dataset']['sha256']=hashlib.sha256(events.read_bytes()).hexdigest()
        raw['experiment'].update(null_replicates=19,optimizer_restarts=1)
        raw['experiment']['sensitivity']['replicates']=1
        path.write_text(json.dumps(raw))
    calls=[]
    def fake(payload,policy):
        calls.append(payload['method'])
        if payload['method']=='GET':
            return {'ok':True,'response':{'data':[{'id':policy.model,'pricing':{'prompt':'0.0000001','completion':'0.0000001'}}]}}
        plan={'decision':'run','reason':'Synthetic fixture','tool_calls':[
            {'tool':'profile_graph','args':{}},{'tool':'community_test','args':{'method':'louvain'}},
            {'tool':'edge_removal_sensitivity','args':{}}]}
        return {'ok':True,'response':{'model':policy.model,'choices':[{'message':{'content':json.dumps(plan)},
            'finish_reason':'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':20,'cost':.000004}}}
    monkeypatch.setattr(live,'broker_request',fake)
    configured=settings.model_copy(update={'api_tool_cache':True})
    with TestClient(create_app(configured,CREDS),base_url='http://127.0.0.1') as client:
        for index in range(2):
            auth=headers()|{'Idempotency-Key':f'fake-live-cache-{index}'}
            job=client.post('/api/v1/jobs',json={'mode':'live','allow_paid':True},headers=auth).json()['job_id']
            jobs=client.app.state.jobs
            jobs.worker.join(40)
            row=jobs.row('alice',job)
            assert row['state']=='completed' and row['billing']=='settled' and row['charged_usd']==.000004
            progress=jobs.public(row)['progress']
            assert progress['llm_calls']==1 and sum(t['cached'] for t in progress['tools'])==(3 if index else 0)
        assert calls==['GET','POST','GET','POST']
        with closing(jobs.db()) as db:
            assert jobs.live_usage(db)==pytest.approx(policy.prior_spend_usd+.000008)
