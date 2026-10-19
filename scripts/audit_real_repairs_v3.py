"""Independent local numerical/artifact checks and receipt-aware cost accounting. No LLM calls."""
from __future__ import annotations
import hashlib,json,math,sqlite3,sys
from pathlib import Path
import networkx as nx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from blackgrid.contracts import RunConfig
from blackgrid.data.collegemsg import build_graph,load_events
from blackgrid.evaluation.scoring import verify_artifacts,numerical_verdict,resolve
from blackgrid.evaluation.sprint4_live import claim_diagnostics
from blackgrid.workflow.api import open_services

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,d):p.write_text(json.dumps(d,indent=2),encoding='utf-8')
OUT=ROOT/'runs/real-repairs-v3-audit';OUT.mkdir(exist_ok=True)
cfg=RunConfig.model_validate_json((ROOT/'runs/real-repairs-v3-fresh/base_config.json').read_text())
graph=build_graph(ROOT,cfg).graph
between=nx.betweenness_centrality(graph)
events=load_events(ROOT/cfg.dataset.path,cfg.dataset.sha256).events
pairs={tuple(sorted((s,t))) for s,t,_ in events if s!=t}
nodes={n for s,t,_ in events for n in (s,t)}
rolling=read(ROOT/'results/sprint06-v2/summary.json')['summary']
phases={}
for phase in ('baseline','verification','fresh','confirmation'):
    batch=ROOT/'runs'/('real-repairs-v3-'+phase)
    freeze=read(batch/'freeze.json');execution=read(batch/'execution.json');rows=[]
    for case in freeze['cases']:
        cid=case['id'];marker=batch/(cid+'.json')
        if not marker.exists():rows.append({'id':cid,'grade':'not_dispatched'});continue
        row=read(marker)
        if 'run_dir' not in row:rows.append(row|{'grade':'incomplete'});continue
        run=Path(row['run_dir'])
        checks={};notes=[]
        try:
            docs=verify_artifacts(run);checks['artifact_hashes']=True
            inv=docs['investigation.json'];report=(run/'report.md').read_text()
            checks['live_mode']=inv['cost']['mode']=='live'
            checks['family_matches']=inv['family']==case['expected_family']
            checks['required_tools']=all(any(t['tool']==name and t['outcome']=='completed' for t in inv['tool_calls'])
                                        for name in case.get('required_tools',[]))
            for claim in inv['reported_claims']:
                for link in claim.get('evidence',[]):resolve(docs,link)
            checks['claim_links_resolve']=True
            diagnostics=[claim_diagnostics(c,docs) for c in inv['reported_claims']]
            checks['claim_numbers_bound']=all(d['numbers_bound'] for d in diagnostics)
            if 'experiment_report.json' in docs:
                checks['independent_null_arithmetic']=numerical_verdict(docs['experiment_report.json'])==docs['experiment_report.json']['verdict']
            if 'node_centrality.json' in docs:
                central=docs['node_centrality.json']
                checks['degree_matches_raw_graph']=all(graph.degree(int(r['node']))==r['degree'] for r in central['rows'])
                checks['betweenness_matches_independent_networkx']=all(math.isclose(between[int(r['node'])],r['betweenness'],abs_tol=1e-12) for r in central['rows'])
            if 'community_bridge.json' in docs:
                partition={int(r['node']):r['community'] for r in docs['community_partition.json']['rows']}
                bridge=docs['community_bridge.json']['rows']
                cross={int(r['node']):sum(partition[n]!=partition[int(r['node'])] for n in graph.neighbors(int(r['node']))) for r in bridge}
                checks['bridge_counts_match_raw_graph']=all(r['cross_degree']==cross[int(r['node'])] for r in bridge)
                checks['bridge_ranks_match']=all(r['bridge_rank']==1+sum(v>cross[int(r['node'])] for v in cross.values()) for r in bridge)
            if 'link_prediction.json' in docs:
                pred=docs['link_prediction.json'];ranking=docs['local_ranking.json'];task=case.get('task',pred['task'])
                checks['forecast_task']=pred['task']==task
                checks['forecast_candidate_count']=pred['candidates']==(len(pairs) if task=='repeat_pair' else len(nodes)*(len(nodes)-1)//2-len(pairs))
                checks['forecast_pair_membership']=all((tuple(sorted(r['pair'])) in pairs)==(task=='repeat_pair') for r in ranking)
                checks['forecast_sorted']=all(a['score']>=b['score'] for a,b in zip(ranking,ranking[1:]))
                checks['forecast_cutoff']=pred['cutoff']==max(t for _,_,t in events)+1
                checks['historical_metrics_match']=all(math.isclose(v['mean_average_precision'],rolling[task]['mean_ap'][m],abs_tol=1e-12) for m,v in docs['prediction_compare.json']['methods'].items())
            if inv['family']=='research' and inv['verdict']!='rejected':
                checks['synthetic_scope_explicit']='saved synthetic' in report
                if 'experiment_decision.json' in docs:
                    checks['decision_cost_net_and_rationale']=all(s in report for s in ('0.0200 utility units','net value -0.0200','no feasible positive net value'))
            refusal=case.get('expected_outcome')=='refuse'
            checks['responsive_or_correct_refusal']=(inv['verdict']=='rejected' and not inv['tool_calls'] and not inv['reported_claims']) if refusal else (inv['verdict']!='rejected' and bool(inv['reported_claims']))
            checks['completed']=row['status']=='completed'
            if refusal:checks['causal_refusal_reason']='causal' in report.lower() or 'influence' in report.lower()
            if cid=='J-X':notes.append('Safe causal refusal, but wrong research metadata label; strict fresh family criterion fails. Corrected only in the later development confirmation, without rescoring this result.')
            row.update(checks=checks,grade='pass' if all(checks.values()) else 'fail',notes=notes,
                       claim_diagnostics=diagnostics)
        except Exception as exc:row.update(grade='audit_failed',error=type(exc).__name__+': '+str(exc))
        rows.append(row)
    phases[phase]={'elapsed_s':execution['elapsed_s'],'source_unchanged_during_run':execution['source_unchanged'],
        'pass':sum(r['grade']=='pass' for r in rows),'fail':sum(r['grade']=='fail' for r in rows),
        'incomplete':sum(r['grade']=='incomplete' for r in rows),'not_dispatched':sum(r['grade']=='not_dispatched' for r in rows),'rows':rows}

conn=sqlite3.connect(ROOT/'runs/workflow.sqlite');conn.row_factory=sqlite3.Row
ops=[dict(r) for r in conn.execute("SELECT operations.*,runs.run_dir FROM operations JOIN runs USING(run_id) WHERE kind='llm'")]
conn.close()
def totals(group):
    known=unknown=0.;count=0;providers=set()
    for op in group:
        path=Path(op['run_dir'])/op['receipt_path'] if op['receipt_path'] else None
        valid=path is not None and path.is_file() and op['receipt_sha256'] and hashlib.sha256(path.read_bytes()).hexdigest()==op['receipt_sha256']
        if valid:
            known+=op['actual_usd'];providers.add(read(path).get('provider','unknown'))
        elif op['state']=='dispatched' or op['category']=='uncertain':
            unknown+=max(op['reserved_usd'],op['actual_usd']);count+=1
    return {'known_receipted_usd':known,'unresolved_reserved_usd':unknown,'unresolved_calls':count,'providers':sorted(providers)}
services=open_services(ROOT/'runs')
try:project,sprint=services.store.spend_elsewhere('__v3_final_audit__')
finally:services.close()
task=totals([o for o in ops if o['run_id'].startswith('real-repairs-v3-')])
result={'phases':phases,'task_accounting':task,'all_history_accounting':totals(ops),
    'project_conservative_usd':project,'sprint_conservative_usd':sprint,'hard_ceiling_usd':3,
    'within_budget':max(project,sprint)<=3,'review':'Independent numerical checks plus code-agent semantic review against frozen criteria; not the running LLM grading itself. No full mock-provider regression suite was executed in this repair task.'}
save(OUT/'audit.json',result)
print(json.dumps({'phase_totals':{k:{f:v[f] for f in ('pass','fail','incomplete','not_dispatched','elapsed_s')} for k,v in phases.items()},
    'task_accounting':task,'project_conservative_usd':project,'within_budget':result['within_budget']},indent=2))
