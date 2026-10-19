"""Receipt and evidence audit of both preserved real repair phases. No model calls."""
import hashlib,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from blackgrid.evaluation.scoring import verify_artifacts,numerical_verdict
from blackgrid.evaluation.sprint4_live import claim_diagnostics
from blackgrid.agent.report import build_report,check_numbers
from blackgrid.agent.roles import InvestigationResult,flatten
from blackgrid.contracts import GraphRecord
from blackgrid.workflow.api import open_services
def read(p):return json.loads(p.read_text())
rows=[]
for phase in ('error-repairs-v5','error-repairs-v5-confirmation'):
    batch=ROOT/'runs'/phase
    for case in read(batch/'freeze.json')['cases']:
        row=read(batch/(case['id']+'.json'));checks={}
        if row['status']=='completed':
            run=Path(row['run_dir']);docs=verify_artifacts(run)
            inv=InvestigationResult.model_validate(docs['investigation.json']);record=GraphRecord.model_validate(docs['graph_record.json'])
            checks['linked_claim_numbers']=all(claim_diagnostics(c,docs)['numbers_bound'] for c in inv.reported_claims)
            report=build_report(inv,flatten(docs),record,case['question'],run.name,'')
            checks['report_numbers']=not check_numbers(report,flatten(docs))
            text=(run/'report.md').read_text()
            checks['family']=row['family']==case['expected_family']
            if row['family']=='forecast':
                checks['actual_history_scope']='full_observed_history' in text and 'scope: first_window' not in text
                checks['actual_evaluation_scope']='two held-out windows' not in text and '5 rolling windows' in text
                checks['task']=docs['link_prediction.json']['task']==case['task']
            if case['id']=='Q-N3':
                checks['both_metrics']=all('ranking_sensitivity.json#/summary/'+m+'_mean_top_jaccard' in flatten(docs) for m in ('degree','betweenness'))
                checks['both_metrics_displayed']=all('Jaccard for '+m in text for m in ('degree','betweenness'))
            if case['id']=='Q-B2':checks['score_formula']="neighbours whose community differs from their own" in text
            if case['id']=='Q-C4':checks['null_arithmetic']=numerical_verdict(docs['experiment_report.json'])==docs['experiment_report.json']['verdict']
        rows.append({'phase':phase,'id':row['id'],'status':row['status'],'reason':row['reason'],'run_dir':row['run_dir'],
            'checks':checks,'pass':row['status']=='completed' and all(checks.values())})
conn=sqlite3.connect(ROOT/'runs/workflow.sqlite');conn.row_factory=sqlite3.Row
ops=[dict(r) for r in conn.execute("SELECT operations.*,runs.run_dir FROM operations JOIN runs USING(run_id) WHERE kind='llm' AND run_id LIKE 'error-repairs-v5-%'")];conn.close()
known=unknown=0.;uncertain=0
for op in ops:
    p=Path(op['run_dir'])/op['receipt_path'] if op['receipt_path'] else None
    valid=p is not None and p.is_file() and op['receipt_sha256'] and hashlib.sha256(p.read_bytes()).hexdigest()==op['receipt_sha256']
    if valid:known+=op['actual_usd']
    elif op['state']=='dispatched' or op['category']=='uncertain':unknown+=max(op['reserved_usd'],op['actual_usd']);uncertain+=1
services=open_services(ROOT/'runs')
try:project,sprint=services.store.spend_elsewhere('__v5_audit__')
finally:services.close()
result={'rows':rows,'known_receipted_usd':known,'unresolved_reserved_usd':unknown,'unresolved_calls':uncertain,'project_conservative_usd':project,
    'within_budget':max(project,sprint)<=3,'phases':{p:read(ROOT/'runs'/p/'execution.json') for p in ('error-repairs-v5','error-repairs-v5-confirmation')}}
(ROOT/'runs/error-repairs-v5-confirmation/audit.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
