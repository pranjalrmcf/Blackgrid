"""Frozen exploratory live evaluation; separate processes protect socket isolation."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import sys, json, time, hashlib, subprocess, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
OUT = ROOT / 'runs' / ('current-system-24-v1-shared-pricing' if '--shared-pricing' in sys.argv else ('current-system-24-v1-network-retry' if '--network-retry' in sys.argv else 'current-system-24-v1'))

def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, default=str), encoding='utf-8')

def worker(case_id):
    started = time.perf_counter()
    from blackgrid.contracts import RunConfig
    from blackgrid.data.collegemsg import build_graph
    from blackgrid.agent.roles import InvestigationInput
    from blackgrid.workflow import runner
    case = next(c for c in json.loads((OUT/'questions.json').read_text()) if c['id']==case_id)
    cfg = json.loads((OUT/'base_config.json').read_text())
    cfg['question'] = case['question']
    config = RunConfig.model_validate(cfg)
    # Presentation is excluded: numerical execution, planning, criticism and reports are unchanged.
    runner.renderer = lambda rt, state: None
    try:
        built = build_graph(ROOT, config)
        inp = InvestigationInput(case_id=built.record.graph_id, question=case['question'],
            request={'method':'auto','family':'auto','planning_mode':config.planning_mode},
            graph=built.graph, record=built.record, spec=config.experiment)
        provider = None
        if '--shared-pricing' in sys.argv:
            from blackgrid.agent.budget import Pricing
            provider = runner.make_provider(config,allow_paid=True,replay_from=None,env_file=ROOT/'.env')
            provider._pricing = Pricing.model_validate_json((OUT/'pricing.json').read_text())
        result = runner.run_investigation(inp, config, provider, ROOT/'runs',
            cache_dir=ROOT/'runs'/'cache', input_ref={'kind':'collegemsg','data_root':str(ROOT)},
            run_prefix='eval24-'+case_id+'-', allow_paid=True,
            reproduce=f'.venv/Scripts/python.exe scripts/evaluate_current_24.py --worker {case_id}')
        save(OUT/(case_id+'.json'), {'id':case_id,'elapsed_s':time.perf_counter()-started,
             'run_dir':str(result.run_dir),'outcome':result.outcome.status})
    except Exception as exc:
        save(OUT/(case_id+'.json'), {'id':case_id,'elapsed_s':time.perf_counter()-started,
            'error':type(exc).__name__+': '+str(exc)[:500]})
        traceback.print_exc()

def main():
    OUT.mkdir(exist_ok=False)
    case_cap=0.05 if '--shared-pricing' in sys.argv else 0.075
    protocol = json.loads((ROOT/'runs/eval-planning-scenarios.json').read_text())
    for c in protocol['cases']:
        if c['id'].startswith('C'):
            c['required_tools'].remove('profile_graph')
    protocol.update({'hard_batch_budget_usd':3 if '--shared-pricing' in sys.argv else 2,'per_case_cap_usd':case_cap,'sum_case_caps_usd':24*case_cap,
        'parallel_processes':24,'external_timeout_s':300,
        'presentation_excluded':True,'numerical_cache':'normal production cache, unchanged keys/specifications',
        'grading_note':'Profile tool optional; community report contains graph facts. Semantic success requires review, not merely completed status.',
        'scope':'Frozen first CollegeMsg window for structure; production forecast uses approved full temporal history; saved synthetic evidence for research.',
        'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').rglob('*.py')}})
    save(OUT/'protocol.json',protocol)
    save(OUT/'questions.json',[{'id':c['id'],'question':c['question']} for c in protocol['cases']])
    cfg = json.loads((ROOT/'configs/collegemsg_live.json').read_text())
    cfg.update({'investigation_family':'auto','planning_mode':'single','deadline_s':240,
        'budget':{'max_usd_total':3.5,'max_usd_current_sprint':3.5,'max_usd_per_investigation':case_cap}})
    cfg['llm']['model']='deepseek/deepseek-v4-flash-0731'
    save(OUT/'base_config.json',cfg)
    if '--shared-pricing' in sys.argv:
        from blackgrid.workflow.runner import make_provider
        from blackgrid.contracts import RunConfig
        provider=make_provider(RunConfig.model_validate(cfg),allow_paid=True,replay_from=None,env_file=ROOT/'.env')
        save(OUT/'pricing.json',provider.pricing().model_dump(mode='json'))
        protocol['pricing_transport']='Single fresh provider pricing lookup reused by all workers; actual completion calls unchanged.'
        save(OUT/'protocol.json',protocol)
    start=time.perf_counter()
    procs=[]
    for c in protocol['cases']:
        log=(OUT/(c['id']+'.log')).open('w',encoding='utf-8')
        args=[sys.executable,__file__,'--worker',c['id']]
        if '--network-retry' in sys.argv: args.append('--network-retry')
        if '--shared-pricing' in sys.argv: args.append('--shared-pricing')
        p=subprocess.Popen(args,cwd=ROOT,stdout=log,stderr=log)
        procs.append((c['id'],p,log))
    print(f'Dispatched all 24 live processes; per-case cap ${case_cap}.',flush=True)
    while any(p.poll() is None for _,p,_ in procs):
        if time.perf_counter()-start>300:
            for cid,p,log in procs:
                if p.poll() is None:
                    p.kill()
                    save(OUT/(cid+'.json'),{'id':cid,'error':'external_timeout; open reservations require reconciliation'})
            break
        time.sleep(1)
    for _,p,log in procs:
        p.wait();log.close()
    save(OUT/'execution.json',{'elapsed_s':time.perf_counter()-start,
         'exit_codes':{cid:p.returncode for cid,p,_ in procs}})
    print(json.dumps({'elapsed_s':time.perf_counter()-start,'results':[json.loads((OUT/(cid+'.json')).read_text()) for cid,_,_ in procs]},indent=2),flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--worker':worker(sys.argv[2])
    else:main()
