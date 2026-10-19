"""Offline artifact integrity and frozen-rubric diagnostics; no model calls."""
import json,sys,hashlib,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from blackgrid.evaluation.scoring import verify_artifacts,numerical_verdict,resolve
OUT=ROOT/'runs/current-system-24-v1-shared-pricing'
protocol=json.loads((OUT/'protocol.json').read_text())
rows=[]
for case in protocol['cases']:
    cid=case['id']; pointer=OUT/(cid+'.json')
    if not pointer.exists():
        rows.append({'id':cid,'status':'running'});continue
    row=json.loads(pointer.read_text());row['question']=case['question']
    if 'run_dir' not in row and 'external_timeout' in row.get('error',''):
        matches=sorted((ROOT/'runs').glob('eval24-'+cid+'-20261018T193700Z-*'))
        if len(matches)==1:
            row['run_dir']=str(matches[0]);row['elapsed_s']=300
            row['directory_link_provenance']='Unique case directory from primary dispatch timestamp; original timeout marker preserved.'
    if 'run_dir' not in row:rows.append(row);continue
    run=Path(row['run_dir'])
    if not (run/'investigation.json').exists():
        state=json.loads((run/'workflow_status.json').read_text())
        row.update({'status':'aborted' if row.get('error') else state.get('status'),'failure_reason':row.get('error') or state.get('reason'),'pause':state.get('pause')})
        rows.append(row);continue
    inv=json.loads((run/'investigation.json').read_text())
    row.update({k:inv[k] for k in ('family','status','failure_reason','verdict','cost','plan_decision','reported_claims','missing_analyses')})
    row['tools']=inv['tool_calls'];row['plan']=inv['plan']
    row['routing_matches']=inv['family']==case['expected_family'] if cid[0]!='X' else None
    row['required_tools_present']=all(any(t['tool']==name and t['outcome']=='completed' for t in inv['tool_calls']) for name in case['required_tools'])
    try:
        docs=verify_artifacts(run);row['artifact_integrity']=True
        row['unresolved_claim_links']=[link for c in inv['reported_claims'] for link in c.get('evidence',[]) if not link.split('#')[0] in docs]
        for c in inv['reported_claims']:
            for link in c.get('evidence',[]):resolve(docs,link)
        if 'experiment_report.json' in docs:
            row['independent_verdict']=numerical_verdict(docs['experiment_report.json'])
            row['verdict_matches']=row['independent_verdict']==docs['experiment_report.json']['verdict']
    except Exception as exc:row['artifact_error']=str(exc)
    rows.append(row)
source_unchanged=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in protocol['source_hashes'].items())
connection=sqlite3.connect(ROOT/'runs/workflow.sqlite')
connection.row_factory=sqlite3.Row
ops=[dict(r) for r in connection.execute("SELECT * FROM operations WHERE run_id LIKE 'eval24-%'")]
connection.close()
batch_ids={Path(r['run_dir']).name for r in rows if 'run_dir' in r}
ops=[o for o in ops if o['run_id'] in batch_ids]
summary={'rows':rows,'source_unchanged':source_unchanged,'operations':ops}
(OUT/'diagnostics.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print('Source unchanged:',source_unchanged)
for r in rows:print(r['id'],r.get('status'),r.get('family',''),r.get('failure_reason') or '', 'tools='+str(r.get('required_tools_present')))
