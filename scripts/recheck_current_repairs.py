"""Offline regressions for the seven exposed failures; never a fresh live pass-rate estimate."""
from __future__ import annotations
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import hashlib,json,subprocess,sys,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
OUT=ROOT/'runs/current-system-repairs-v2-offline'
IDS=('C03','R02','R04','X02','X03','F02','F04')

def save(path,obj):path.write_text(json.dumps(obj,indent=2),encoding='utf-8')

def worker(cid):
    from blackgrid.contracts import RunConfig
    from blackgrid.data.collegemsg import build_graph
    from blackgrid.agent.roles import InvestigationInput
    from blackgrid.agent.providers import MockProvider
    from blackgrid.workflow import runner
    question=next(c['question'] for c in json.loads((OUT/'questions.json').read_text()) if c['id']==cid)
    cfg=json.loads((ROOT/'configs/collegemsg_live.json').read_text())
    cfg.update(mode='mock',paid_execution_authorized=False,investigation_family='auto',question=question,deadline_s=240,
        budget={'max_usd_total':0,'max_usd_current_sprint':0,'max_usd_per_investigation':0})
    config=RunConfig.model_validate(cfg)
    built=build_graph(ROOT,config)
    inp=InvestigationInput(case_id=built.record.graph_id,question=question,
        request={'family':'auto','method':'auto'},graph=built.graph,record=built.record,spec=config.experiment)
    runner.renderer=lambda rt,state:None
    out=runner.run_investigation(inp,config,MockProvider(),OUT/'runs',cache_dir=ROOT/'runs/cache',
        input_ref={'kind':'collegemsg','data_root':str(ROOT)},run_prefix='repair-v2-'+cid+'-',
        reproduce=f'.venv/Scripts/python.exe scripts/recheck_current_repairs.py --worker {cid}')
    save(OUT/(cid+'.json'),{'id':cid,'run_dir':str(out.run_dir),'status':out.outcome.status})

def main():
    OUT.mkdir(exist_ok=False)
    # Free-only isolated ledger: historical live reservations remain untouched in the main store.
    (OUT/'runs').mkdir()
    for name in ('sprint6-v1','forecast_models'):
        shutil.copytree(ROOT/'runs'/name,OUT/'runs'/name)
    cases=[c for c in json.loads((ROOT/'runs/eval-planning-scenarios.json').read_text())['cases'] if c['id'] in IDS]
    save(OUT/'questions.json',[{'id':c['id'],'question':c['question']} for c in cases])
    save(OUT/'freeze.json',{'version':'current-system-repairs-v2','mode':'mock','paid_execution':False,
        'cases_previously_inspected':True,'purpose':'Development regressions only; not a new live evaluation',
        'presentation_excluded':True,'numerical_cache':'Unchanged production cache keys/specifications',
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').rglob('*.py')}})
    started=time.perf_counter();jobs=[]
    for cid in IDS:
        log=(OUT/(cid+'.log')).open('w',encoding='utf-8')
        jobs.append((cid,subprocess.Popen([sys.executable,__file__,'--worker',cid],cwd=ROOT,stdout=log,stderr=log),log))
    print('Seven offline regressions dispatched in separate processes; no paid provider.',flush=True)
    for cid,p,log in jobs:
        try:p.wait(timeout=max(1,300-(time.perf_counter()-started)))
        except subprocess.TimeoutExpired:p.kill();p.wait()
        log.close()
    from blackgrid.evaluation.scoring import verify_artifacts,numerical_verdict
    rows=[]
    for cid,p,_ in jobs:
        marker=OUT/(cid+'.json')
        if not marker.exists():rows.append({'id':cid,'pass':False,'exit_code':p.returncode});continue
        row=json.loads(marker.read_text());run=Path(row['run_dir']);docs=verify_artifacts(run)
        inv=docs['investigation.json'];report=(run/'report.md').read_text()
        checks={'completed':row['status']=='completed','free':inv['cost']['actual_usd']==0}
        if cid=='C03':checks.update(correct_family=inv['family']=='community',
            null_arithmetic='experiment_report.json' in docs and numerical_verdict(docs['experiment_report.json'])==docs['experiment_report.json']['verdict'])
        elif cid=='R02':checks['cost_and_net_value']='0.0200 utility units' in report and 'net value -0.0200' in report
        elif cid=='R04':checks['estimand_and_assumptions']=all(s in report for s in ('estimand is ATE','adjustment set is X','supplied assumptions, not empirically verified'))
        elif cid in ('X02','X03'):checks.update(refused=inv['verdict']=='rejected',no_substitution=not inv['tool_calls'] and not inv['llm_calls'])
        else:checks.update(forecast=inv['family']=='forecast',has_ranking=bool(docs['local_ranking.json']),
            no_interpretation_request=all(c['role']=='planner' for c in inv['llm_calls']),
            checked_claims=bool(inv['reported_claims']) and all(d['accepted'] for d in inv['critic_decisions']))
        row.update(checks=checks,passed=all(checks.values()),llm_roles=[c['role'] for c in inv['llm_calls']]);rows.append(row)
    frozen=json.loads((OUT/'freeze.json').read_text())['source_hashes']
    summary={'mode':'mock','previously_inspected_cases':True,'elapsed_s':time.perf_counter()-started,
        'passed':sum(r.get('passed',False) for r in rows),'cases':len(rows),'actual_usd':0,
        'source_unchanged_during_run':all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in frozen.items()),'rows':rows}
    save(OUT/'summary.json',summary);print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':
    if len(sys.argv)>1:worker(sys.argv[2])
    else:main()
