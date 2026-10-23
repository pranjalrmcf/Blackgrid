"""Registered same-input uncached/cold/warm API comparison in isolated mock state."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import random
import resource
import sqlite3
import statistics
import time
from datetime import datetime
from pathlib import Path
from fastapi.testclient import TestClient
from blackgrid.operations.api import create_app,Client
from blackgrid.operations.settings import Settings
from blackgrid.analysis.parity import fingerprint
from tests.test_api import CREDS,headers


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition',choices=('baseline','candidate'),required=True)
    args=parser.parse_args()
    protocol_path=Path('/app/protocols/production_phase8_v1.json')
    protocol=json.loads(protocol_path.read_bytes())
    random.seed(protocol['seed'])
    output=Path('/evidence')/(args.condition+'.json')
    assert not output.exists(),'preserve the previous comparison; register another attempt'
    root=Path('/tmp/phase8')
    (root/'runs/cache').mkdir(parents=True)
    config_path=Path('/bench/public/stochastic_block-100.json')
    values=dict(environment='test',config=config_path,data_root=Path('/bench/public'),runs_dir=root/'runs')
    if args.condition=='candidate': values['api_tool_cache']=True
    settings=Settings(**values)
    reference = json.loads(Path('/evidence/baseline.json').read_bytes())['jobs'][0] if args.condition=='candidate' else None
    rows=[]
    started=time.perf_counter()
    error=None
    tokens={f'cold-{i}':('phase8-cold-'+str(i)).ljust(40,'x') for i in range(3)}
    credentials=CREDS.model_copy(update={'clients':CREDS.clients+tuple(
        Client(subject=owner,token_sha256=hashlib.sha256(token.encode()).hexdigest()) for owner,token in tokens.items())})
    try:
        with TestClient(create_app(settings,credentials),base_url='http://127.0.0.1') as client:
            cases=([('uncached','alice')]*3 if args.condition=='baseline' else
                   [('cold_cache',f'cold-{i}') for i in range(3)]+[('prime','alice')]+[('warm_cache','alice')]*3)
            # Both images use the same fixed fake credential registry. Every case
            # traverses the same authenticated API routes; owners isolate cold entries.
            for index,(condition,owner) in enumerate(cases):
                if time.perf_counter()-started>protocol['max_total_seconds']: raise RuntimeError('comparison deadline')
                submit_owner=owner
                auth=(headers() if owner=='alice' else {'Authorization':'Bearer '+tokens[owner]})|{'Idempotency-Key':f'phase8-{index}'}
                before=time.perf_counter()
                reply=client.post('/api/v1/jobs',json={'question':protocol['question']},headers=auth)
                assert reply.status_code==202,reply.status_code
                job=reply.json()['job_id']
                jobs=client.app.state.jobs
                jobs.worker.join(protocol['max_job_seconds'])
                assert not jobs.worker.is_alive(),'job deadline'
                row=client.get(f'/api/v1/jobs/{job}',headers=auth).json()
                assert row['state']=='completed',row['error_code']
                result=client.get(f'/api/v1/jobs/{job}/results',headers=auth).json()
                result.pop('job_id')
                fp=fingerprint(jobs.run_folder(submit_owner,job))
                if reference is None and not rows: reference=dict(result=result,fingerprint=fp)
                assert result==reference['result'] and fp==reference['fingerprint'],'scientific or LLM counters changed'
                assert result['summary']['actual_usd']==0 and result['summary']['llm_calls']==1
                hits=sum(t.get('cached',False) for t in row['progress']['tools'])
                assert hits==(3 if condition=='warm_cache' else 0),('unexpected cache state',condition,hits)
                def seconds(a,b): return (datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()
                rows.append(dict(condition=condition,wall_seconds=time.perf_counter()-before,
                    creation_to_terminal_seconds=seconds(row['created_utc'],row['completed_utc']),
                    queue_seconds=seconds(row['created_utc'],row['started_utc']),cache_hits=hits,
                    attempts=row['attempts'],result=result,fingerprint=fp))
    except Exception as exc:
        error=type(exc).__name__
        raise
    finally:
        usage=resource.getrusage(resource.RUSAGE_SELF)
        report=dict(version=protocol['version'],condition=args.condition,state='failed' if error else 'completed',
            error_category=error,protocol_sha256=hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
            config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),jobs=rows,
            medians={c:statistics.median(r['creation_to_terminal_seconds'] for r in rows if r['condition']==c)
                     for c in sorted({r['condition'] for r in rows})},
            elapsed_seconds=time.perf_counter()-started,python=platform.python_version(),sqlite=sqlite3.sqlite_version,
            packages={n:importlib.metadata.version(n) for n in ('networkx','numpy','scipy')},
            source_hashes={p.relative_to('/app').as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(Path('/app/src').rglob('*.py'))},
            parent_cpu_seconds=usage.ru_utime+usage.ru_stime,parent_peak_rss_bytes=usage.ru_maxrss*1024,
            actual_usd=0,real_provider_calls=0,
            limitations=['small exploratory repeated-input fixture','ASGI test client, not network/TLS load',
                'one real contained worker process per job','instrumented graph profile is separate',
                'no real-provider inference or general cold-speed claim'])
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({k:report[k] for k in ('condition','state','medians','elapsed_seconds')}))


if __name__=='__main__': main()
