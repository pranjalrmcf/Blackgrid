"""Frozen, one-attempt full live evaluation; no production modifications."""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import hashlib,json,subprocess,sys,time
from pathlib import Path
from verify_real_repairs_v3 import worker,save,ROOT
sys.path.insert(0,str(ROOT/'src'))

def main():
    from blackgrid.contracts import RunConfig
    from blackgrid.workflow.runner import make_provider
    from blackgrid.workflow.api import open_services
    out=ROOT/'runs/error-repairs-v5';out.mkdir(exist_ok=False)
    protocol=ROOT/'protocols/error_repairs_v5.json'
    cases=json.loads(protocol.read_text())['cases'];cap=.05
    services=open_services(ROOT/'runs')
    try:project,sprint=services.store.spend_elsewhere('__v4_preflight__')
    finally:services.close()
    if max(project,sprint)+len(cases)*cap>3:raise RuntimeError('Insufficient remaining budget for disjoint case caps')
    cfg=json.loads((ROOT/'configs/collegemsg_live.json').read_text())
    cfg.update(mode='live',paid_execution_authorized=True,investigation_family='auto',planning_mode='single',deadline_s=180,
        budget={'max_usd_total':3,'max_usd_current_sprint':3,'max_usd_per_investigation':cap,'max_llm_calls':4,'max_retries_per_call':0,'max_revision_rounds':1})
    cfg['llm'].update(model='deepseek/deepseek-v4-flash-0731',max_tokens_per_call=8192,reasoning_max_tokens=1024,request_timeout_s=60)
    save(out/'base_config.json',cfg)
    save(out/'questions.json',[{'id':c['id'],'question':c['question']} for c in cases])
    paths=list((ROOT/'src').rglob('*.py'))+[Path(__file__),ROOT/'scripts/verify_real_repairs_v3.py',ROOT/'scripts/audit_current_eval_v4.py',protocol]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    save(out/'freeze.json',{'cases':cases,'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'historical_accounted_usd':project,
        'historical_sprint_usd':sprint,'hard_project_ceiling_usd':3,'per_case_cap_usd':cap,'case_caps_sum_usd':len(cases)*cap,
        'parallel_workers':4,'external_timeout_s':240,'source_hashes':hashes,'attempts':1})
    provider=make_provider(RunConfig.model_validate(cfg),allow_paid=True,replay_from=None,env_file=ROOT/'.env')
    save(out/'pricing.json',provider.pricing().model_dump(mode='json'))
    started=time.perf_counter();pending=list(cases);active=[];finished=[]
    while pending or active:
        while pending and len(active)<4:
            c=pending.pop(0);log=(out/(c['id']+'.log')).open('w',encoding='utf-8')
            p=subprocess.Popen([sys.executable,__file__,'--worker',str(out),c['id']],cwd=ROOT,stdout=log,stderr=log)
            active.append((c['id'],p,log,time.perf_counter()))
        for cid,p,log,t in list(active):
            if p.poll() is None and time.perf_counter()-t>240:
                p.kill();p.wait();save(out/(cid+'.json'),{'id':cid,'error':'external_timeout; retain dispatched reservations'})
            if p.poll() is not None:
                log.close();active.remove((cid,p,log,t));finished.append(cid)
                marker=out/(cid+'.json')
                if not marker.exists():save(marker,{'id':cid,'error':'worker exited without result'})
                row=json.loads(marker.read_text())
                print(json.dumps({k:row.get(k) for k in ('id','status','family','verdict','error','elapsed_s')}),flush=True)
        time.sleep(.2)
    save(out/'execution.json',{'elapsed_s':time.perf_counter()-started,'finished':finished,'not_dispatched':[],
        'source_unchanged':all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items())})
    print('Finished '+str(out),flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3])
    else:main()
