"""Independent aggregate checks of saved evaluation evidence. No network or model calls."""
import json,sys,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from blackgrid.data.collegemsg import load_events
from blackgrid.evaluation.scoring import numerical_verdict,verify_artifacts
OUT=ROOT/'runs/current-system-24-v1-shared-pricing'
protocol=json.loads((OUT/'protocol.json').read_text())
cfg=json.loads((OUT/'base_config.json').read_text())
table=load_events(ROOT/cfg['dataset']['path'],cfg['dataset']['sha256'])
pairs={tuple(sorted((s,t))) for s,t,_ in table.events if s!=t}
nodes={n for s,t,_ in table.events for n in (s,t)}
rolling=json.loads((ROOT/'results/sprint06-v2/summary.json').read_text())
rows=[]
for case in protocol['cases']:
    if case['id'][0] not in 'CF':continue
    pointer=OUT/(case['id']+'.json')
    if not pointer.exists():continue
    marker=json.loads(pointer.read_text())
    if 'run_dir' not in marker:continue
    run=Path(marker['run_dir'])
    row={'id':case['id'],'checks':{}}
    try:
        if not (run/'manifest.json').exists():
            row['status']='incomplete_manifest';rows.append(row);continue
        docs=verify_artifacts(run);row['checks']['manifest_hashes']=True
        if 'experiment_report.json' in docs:
            exp=docs['experiment_report.json'];row['checks']['null_arithmetic']=numerical_verdict(exp)==exp['verdict']
        if 'link_prediction.json' in docs:
            pred=docs['link_prediction.json'];task=case['task'];rank=docs['local_ranking.json']
            row['checks']['task_matches']=pred['task']==task
            count=len(pairs) if task=='repeat_pair' else len(nodes)*(len(nodes)-1)//2-len(pairs)
            row['checks']['candidate_count']=pred['candidates']==count
            row['checks']['historical_pair_membership']=all((tuple(sorted(r['pair'])) in pairs)==(task=='repeat_pair') for r in rank)
            row['checks']['sorted_scores']=all(a['score']>=b['score'] for a,b in zip(rank,rank[1:]))
            row['checks']['unique_pairs']=len({tuple(sorted(r['pair'])) for r in rank})==len(rank)
            # Frozen temporal contract uses an exclusive boundary, one second after final event.
            row['checks']['cutoff_matches']=pred['cutoff']==1+max(t for _,_,t in table.events)
            comparison=docs['prediction_compare.json']
            row['checks']['rolling_metrics_match']=all(math.isclose(v['mean_average_precision'],rolling['summary'][task]['mean_ap'][m],abs_tol=1e-12) for m,v in comparison['methods'].items())
            row['ranked_pairs']=len(rank)
        row['passed']=all(row['checks'].values())
    except Exception as exc:row['error']=str(exc);row['passed']=False
    rows.append(row)
(OUT/'independent-numerical-checks.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps(rows,indent=2))
