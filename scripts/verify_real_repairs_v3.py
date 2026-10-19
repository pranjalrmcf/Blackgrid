"""Real-provider-only, bounded repair diagnostics. No mock/replay execution path."""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import hashlib,json,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))

def save(path,obj):path.write_text(json.dumps(obj,indent=2,default=str),encoding='utf-8')

def worker(batch,cid):
    from blackgrid.contracts import RunConfig
    from blackgrid.agent.budget import Pricing
    from blackgrid.agent.roles import InvestigationInput
    from blackgrid.data.collegemsg import build_graph
    from blackgrid.workflow import runner
    started=time.perf_counter();out=Path(batch)
    case=next(c for c in json.loads((out/'questions.json').read_text()) if c['id']==cid)
    cfg=json.loads((out/'base_config.json').read_text());cfg['question']=case['question']
    config=RunConfig.model_validate(cfg)
    assert config.mode.value=='live' and config.paid_execution_authorized
    provider=runner.make_provider(config,allow_paid=True,replay_from=None,env_file=ROOT/'.env')
    assert provider.name=='openrouter'
    provider._pricing=Pricing.model_validate_json((out/'pricing.json').read_text())
    runner.renderer=lambda rt,state:None
    try:
        built=build_graph(ROOT,config)
        inp=InvestigationInput(case_id=built.record.graph_id,question=case['question'],
            request={'method':'auto','family':'auto','planning_mode':'single'},
            graph=built.graph,record=built.record,spec=config.experiment)
        result=runner.run_investigation(inp,config,provider,ROOT/'runs',cache_dir=ROOT/'runs/cache',
            input_ref={'kind':'collegemsg','data_root':str(ROOT)},run_prefix=out.name+'-'+cid+'-',allow_paid=True)
        row={'id':cid,'elapsed_s':time.perf_counter()-started,'run_dir':str(result.run_dir),
            'status':result.outcome.status,'reason':result.outcome.reason}
        if result.result:
            inv=result.result.model_dump(mode='json')
            row.update({k:inv[k] for k in ('family','verdict','plan','plan_decision','cost','reported_claims','tool_calls','missing_analyses')})
        save(out/(cid+'.json'),row)
    except Exception as exc:
        save(out/(cid+'.json'),{'id':cid,'error':type(exc).__name__+': '+str(exc)[:500]})
        traceback.print_exc()

def main(phase):
    from blackgrid.contracts import RunConfig
    from blackgrid.workflow.runner import make_provider
    from blackgrid.workflow.api import open_services
    out=ROOT/'runs'/('real-repairs-v3-'+phase)
    out.mkdir(exist_ok=False)
    case_source=ROOT/'protocols'/('real_repairs_v3_confirmation.json' if phase=='confirmation' else
        'real_repairs_v3_fresh.json' if phase=='fresh' else 'current_system_eval_v2.json')
    cases=json.loads(case_source.read_text())['cases']
    cap=.05 if phase=='verification' else .04
    if phase=='baseline':cases=[c for c in cases if c['id'] in ('V-C03','V-N01','V-B02')]
    elif phase not in ('verification','fresh','confirmation'):raise ValueError('unknown phase')
    services=open_services(ROOT/'runs')
    try:project,sprint=services.store.spend_elsewhere('__real_v3_preflight__')
    finally:services.close()
    if max(project,sprint)+len(cases)*cap>3:raise RuntimeError('Conservative disjoint case caps exceed remaining $3 project budget')
    cfg=json.loads((ROOT/'configs/collegemsg_live.json').read_text())
    cfg.update(mode='live',paid_execution_authorized=True,investigation_family='auto',planning_mode='single',deadline_s=180,
        budget={'max_usd_total':3,'max_usd_current_sprint':3,'max_usd_per_investigation':cap,
                'max_llm_calls':4,'max_retries_per_call':0,'max_revision_rounds':1})
    cfg['llm'].update(model='deepseek/deepseek-v4-flash-0731',max_tokens_per_call=4096,
        reasoning_max_tokens=1024,request_timeout_s=120 if phase=='verification' else 60)
    save(out/'base_config.json',cfg)
    save(out/'questions.json',[{'id':c['id'],'question':c['question']} for c in cases])
    save(out/'freeze.json',{'phase':phase,'mode':'live','provider':'openrouter','cases_previously_inspected':phase!='fresh',
        'case_protocol_sha256':hashlib.sha256(case_source.read_bytes()).hexdigest(),
        'cases':cases,'historical_accounted_usd':project,'hard_project_ceiling_usd':3,'per_case_cap_usd':cap,
        'case_caps_sum_usd':len(cases)*cap,'parallel_workers':4,'external_timeout_s':210,
        'numerics':'Unchanged production tools/specifications; normal cache and saved forecast parameters',
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').rglob('*.py')}})
    provider=make_provider(RunConfig.model_validate(cfg),allow_paid=True,replay_from=None,env_file=ROOT/'.env')
    save(out/'pricing.json',provider.pricing().model_dump(mode='json'))
    started=time.perf_counter();pending=list(cases);active=[];finished=[];stopped=False
    while pending or active:
        while pending and len(active)<4 and not stopped:
            c=pending.pop(0);log=(out/(c['id']+'.log')).open('w',encoding='utf-8')
            p=subprocess.Popen([sys.executable,__file__,'--worker',str(out),c['id']],cwd=ROOT,stdout=log,stderr=log)
            active.append((c['id'],p,log,time.perf_counter()))
        for cid,p,log,t in list(active):
            if p.poll() is None and time.perf_counter()-t>210:
                p.kill();p.wait()
                save(out/(cid+'.json'),{'id':cid,'error':'external_timeout; retain dispatched reservations'})
            if p.poll() is not None:
                log.close();active.remove((cid,p,log,t));finished.append(cid)
                marker=out/(cid+'.json')
                row=json.loads(marker.read_text()) if marker.exists() else {'id':cid,'error':'worker exited'}
                print(json.dumps({k:row.get(k) for k in ('id','status','family','verdict','error','elapsed_s')}),flush=True)
                if row.get('status')=='paused' or 'external_timeout' in row.get('error',''):
                    stopped=True
        if stopped and not active:break
        time.sleep(.2)
    frozen=json.loads((out/'freeze.json').read_text())['source_hashes']
    save(out/'execution.json',{'elapsed_s':time.perf_counter()-started,'finished':finished,
        'not_dispatched':[c['id'] for c in pending],'stopped_for_unknown_billing':stopped,
        'source_unchanged':all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in frozen.items())})
    print('Finished '+str(out),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3])
    else:main(sys.argv[1])
