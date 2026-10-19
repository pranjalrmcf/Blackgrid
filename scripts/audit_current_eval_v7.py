"""Independent evidence/numerical evaluation, with no model calls."""
from __future__ import annotations
import hashlib,json,math,sqlite3,sys,statistics
from pathlib import Path
import networkx as nx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from blackgrid.contracts import RunConfig
from blackgrid.data.collegemsg import build_graph,load_events
from blackgrid.evaluation.scoring import verify_artifacts,numerical_verdict,resolve
from blackgrid.evaluation.sprint4_live import claim_diagnostics
from blackgrid.workflow.api import open_services
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    out=ROOT/'runs/current-system-eval-v7';freeze=read(out/'freeze.json');execution=read(out/'execution.json')
    cfg=RunConfig.model_validate_json((out/'base_config.json').read_text());graph=build_graph(ROOT,cfg).graph
    between=nx.betweenness_centrality(graph)
    events=load_events(ROOT/cfg.dataset.path,cfg.dataset.sha256).events
    pairs={tuple(sorted((s,t))) for s,t,_ in events if s!=t};nodes={n for s,t,_ in events for n in (s,t)}
    rolling=read(ROOT/'results/sprint06-v2/summary.json')['summary'];rows=[]
    for case in freeze['cases']:
        marker=out/(case['id']+'.json');row=read(marker) if marker.exists() else {'id':case['id'],'error':'not dispatched'}
        checks={}
        if 'run_dir' not in row or row.get('status')!='completed':
            rows.append(row|{'grade':'incomplete'});continue
        try:
            run=Path(row['run_dir']);docs=verify_artifacts(run);inv=docs['investigation.json'];report=(run/'report.md').read_text()
            checks.update(artifact_hashes=True,live_mode=inv['cost']['mode']=='live',family_matches=inv['family']==case['expected_family'],source_frozen=execution['source_unchanged'])
            checks['required_tools']=all(any(t['tool']==name and t['outcome']=='completed' for t in inv['tool_calls']) for name in case['required_tools'])
            for c in inv['reported_claims']:
                for link in c.get('evidence',[]):resolve(docs,link)
            checks['claim_links_resolve']=True
            diagnostics=[claim_diagnostics(c,docs) for c in inv['reported_claims']]
            checks['claim_numbers_bound']=all(d['numbers_bound'] for d in diagnostics)
            if 'experiment_report.json' in docs:checks['independent_null_arithmetic']=numerical_verdict(docs['experiment_report.json'])==docs['experiment_report.json']['verdict']
            if 'node_centrality.json' in docs:
                checks['degree_matches_raw_graph']=all(graph.degree(int(r['node']))==r['degree'] for r in docs['node_centrality.json']['rows'])
                checks['betweenness_matches_networkx']=all(math.isclose(between[int(r['node'])],r['betweenness'],abs_tol=1e-12) for r in docs['node_centrality.json']['rows'])
            if 'community_bridge.json' in docs:
                partition={int(r['node']):r['community'] for r in docs['community_partition.json']['rows']};bridge=docs['community_bridge.json']['rows']
                cross={int(r['node']):sum(partition[n]!=partition[int(r['node'])] for n in graph.neighbors(int(r['node']))) for r in bridge}
                checks['bridge_counts_match']=all(r['cross_degree']==cross[int(r['node'])] for r in bridge)
                checks['bridge_ranks_match']=all(r['bridge_rank']==1+sum(v>cross[int(r['node'])] for v in cross.values()) for r in bridge)
            if 'link_prediction.json' in docs:
                pred=docs['link_prediction.json'];ranking=docs['local_ranking.json'];task=case.get('task',pred['task'])
                checks['forecast_task']=pred['task']==task
                checks['forecast_candidate_count']=pred['candidates']==(len(pairs) if task=='repeat_pair' else len(nodes)*(len(nodes)-1)//2-len(pairs))
                checks['forecast_pair_membership']=all((tuple(sorted(r['pair'])) in pairs)==(task=='repeat_pair') for r in ranking)
                checks['forecast_sorted']=all(a['score']>=b['score'] for a,b in zip(ranking,ranking[1:]))
                checks['forecast_cutoff']=pred['cutoff']==max(t for _,_,t in events)+1
                checks['historical_metrics_match']=all(math.isclose(v['mean_average_precision'],rolling[task]['mean_ap'][m],abs_tol=1e-12) for m,v in docs['prediction_compare.json']['methods'].items())
            from blackgrid.agent.report import build_report,check_numbers
            from blackgrid.agent.roles import InvestigationResult,flatten
            from blackgrid.contracts import GraphRecord
            checks['report_numbers_bound']=not check_numbers(build_report(InvestigationResult.model_validate(inv),flatten(docs),GraphRecord.model_validate(docs['graph_record.json']),case['question'],run.name,''),flatten(docs))
            if inv['family']=='forecast':
                checks['report_scope']='full_observed_history' in report and 'scope: first_window' not in report
                checks['evaluation_scope']='two held-out windows' not in report and '5 rolling windows' in report and 'development' in report
            if case['id']=='T-N3':
                checks['both_stability_metrics']=all(k+'_mean_top_jaccard' in docs['ranking_sensitivity.json']['summary'] for k in ('degree','betweenness'))
                checks['both_stability_metrics_displayed']=all('Jaccard for '+k in report for k in ('degree','betweenness'))
            if case['id']=='T-B2':checks['connector_formula']="neighbours whose community differs from their own" in report
            if case['expected_family']=='bridge' and 'ranking_sensitivity' in case['required_tools']:
                checks['bridge_stability_target']=docs.get('ranking_sensitivity.json',{}).get('summary',{}).get('metric')=='cross_degree'
            if inv['family']=='research' and inv['verdict']!='rejected':
                checks['synthetic_scope_explicit']='saved synthetic' in report
                if 'experiment_decision.json' in docs:checks['decision_cost_net_rationale']=all(s in report for s in ('0.0200 utility units','net value -0.0200','no feasible positive net value'))
            refusal=case.get('expected_outcome')=='refuse'
            checks['responsive_or_correct_refusal']=(inv['verdict']=='rejected' and not inv['tool_calls'] and not inv['reported_claims']) if refusal else (inv['verdict']!='rejected' and bool(inv['reported_claims']))
            rows.append(row|{'checks':checks,'automated_grade':'pass' if all(checks.values()) else 'fail','grade':'pending_semantic_review','claim_diagnostics':diagnostics})
        except Exception as exc:rows.append(row|{'grade':'audit_failed','error':type(exc).__name__+': '+str(exc)})
    conn=sqlite3.connect(ROOT/'runs/workflow.sqlite');conn.row_factory=sqlite3.Row
    ops=[dict(r) for r in conn.execute("SELECT operations.*,runs.run_dir FROM operations JOIN runs USING(run_id) WHERE kind='llm' AND run_id LIKE 'current-system-eval-v7-%'")];conn.close()
    known=unknown=0.;uncertain=0
    for op in ops:
        p=Path(op['run_dir'])/op['receipt_path'] if op['receipt_path'] else None
        valid=p is not None and p.is_file() and op['receipt_sha256'] and hashlib.sha256(p.read_bytes()).hexdigest()==op['receipt_sha256']
        if valid:known+=op['actual_usd']
        elif op['state']=='dispatched' or op['category']=='uncertain':unknown+=max(op['reserved_usd'],op['actual_usd']);uncertain+=1
    services=open_services(ROOT/'runs')
    try:project,sprint=services.store.spend_elsewhere('__v4_final__')
    finally:services.close()
    times=sorted(r['elapsed_s'] for r in rows if 'elapsed_s' in r)
    result={'rows':rows,'execution':execution,'accounting':{'known_receipted_usd':known,'unresolved_reserved_usd':unknown,'unresolved_calls':uncertain,'recorded_llm_operations':len(ops),'project_conservative_usd':project,'sprint_conservative_usd':sprint,'within_budget':max(project,sprint)<=3},'latency':{'median_s':statistics.median(times),'p90_s':times[math.ceil(.9*len(times))-1],'max_s':max(times)}}
    (out/'audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'automated_pass':sum(r.get('automated_grade')=='pass' for r in rows),'incomplete':sum(r['grade']=='incomplete' for r in rows),'failed_checks':{r['id']:[k for k,v in r.get('checks',{}).items() if not v] for r in rows if r.get('automated_grade')!='pass'},'accounting':result['accounting'],'latency':result['latency']},indent=2))
if __name__=='__main__':main()
