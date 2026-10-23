"""Reconcile the frozen small comparison and sanitized observed span breakdown."""
import hashlib
import json
import math
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/production_phase8'


def main():
    before=json.loads((OUT/'comparison-v1/baseline.json').read_bytes())
    after=json.loads((OUT/'comparison-v1/candidate.json').read_bytes())
    assert before['state']==after['state']=='completed'
    assert before['protocol_sha256']==after['protocol_sha256']
    assert before['config_sha256']==after['config_sha256']
    assert before['python']==after['python'] and before['sqlite']==after['sqlite'] and before['packages']==after['packages']
    rows=before['jobs']+after['jobs']
    assert len(rows)==10 and all(r['fingerprint']==rows[0]['fingerprint'] and r['result']==rows[0]['result'] for r in rows)
    groups={c:[r for r in rows if r['condition']==c] for c in ('uncached','cold_cache','prime','warm_cache')}
    assert [len(groups[c]) for c in groups]==[3,3,1,3]
    medians={c:statistics.median(r['creation_to_terminal_seconds'] for r in group) for c,group in groups.items()}
    breakdown={}
    api_samples={}
    for report,name in ((before,'baseline'),(after,'candidate')):
        events=[]
        for line in (OUT/f'comparison-v1/{name}.log').read_text().splitlines():
            if line.startswith('{'):
                try: events.append(json.loads(line))
                except ValueError: pass
        identities=list(dict.fromkeys(e['job_id'] for e in events if e.get('name')=='job_scheduling' and e.get('event')=='start'))
        assert len(identities)==len(report['jobs'])
        for job,row in zip(identities,report['jobs']):
            ends=[e for e in events if e.get('job_id')==job and e.get('event')=='end']
            measured={label:sum(e['duration_s'] for e in ends if e.get('name')==span)
                      for label,span in (('tools','tool_call'),('workflow','agent_execution'),('mock_llm','llm_call'),
                                         ('mock_provider','provider_request'),('artifact_persistence','artifact_persistence'))}
            measured['outside_workflow_seconds']=max(0,row['creation_to_terminal_seconds']-measured['workflow'])
            measured['workflow_other_seconds']=max(0,measured['workflow']-measured['tools']-measured['mock_llm']-measured['artifact_persistence'])
            measured['observed_job_span_peak_rss_bytes']=max((e.get('peak_rss_bytes') or 0 for e in ends),default=0)
            breakdown.setdefault(row['condition'],[]).append(measured)
        api_samples[name]={route:[e['duration_s'] for e in events if e.get('component')=='api' and
            e.get('event')=='request_completed' and e.get('route')==route] for route in
            ('/api/v1/jobs','/api/v1/jobs/{job_id}','/api/v1/jobs/{job_id}/results')}
    summary=dict(version='production-phase8-v1',jobs=10,scientific_fingerprint_exact=True,api_result_exact=True,
        llm_call_token_and_cost_counters_exact=True,real_provider_calls=0,actual_usd=0,
        creation_to_terminal_medians=medians,warm_reduction_fraction=1-medians['warm_cache']/medians['uncached'],
        cold_change_fraction=medians['cold_cache']/medians['uncached']-1,
        raw_samples={c:[r['creation_to_terminal_seconds'] for r in group] for c,group in groups.items()},
        span_breakdown=breakdown,api_route_seconds=api_samples,
        limitations=['three timed samples per condition; exploratory, no confidence interval or production SLO',
            'warm-cache reuse only; no cold-algorithm or LLM inference speed claim',
            'sequential ASGI client; no TLS/network or concurrent capacity claim',
            'host not dedicated; separate limited regression container also ran during candidate',
            'workflow spans include child work; do not add nested categories together',
            'workflow_other is an unattributed residual including startup/checkpoint work, not a direct import or SQL timing',
            'no isolated SQL query or real-provider CPU/latency measurement'])
    (OUT/'comparison-v1/summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('span_breakdown','api_route_seconds')},indent=2))


if __name__=='__main__': main()
