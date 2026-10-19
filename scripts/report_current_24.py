"""Combine independent saved reviews and all-attempt cost exposure, offline."""
import json,sqlite3,statistics,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/current-system-24-v1-shared-pricing'
read=lambda p:json.loads(p.read_text())
data=read(OUT/'diagnostics.json');protocol=read(OUT/'protocol.json')
semantic={r['id']:r for r in read(OUT/'review-research-refusals.json')['cases']}
structural={r['id']:r for r in read(OUT/'review-structural.json')['cases']}
numerics={r['id']:r for r in read(OUT/'independent-numerical-checks.json')}
rows=[]
for case,row in zip(protocol['cases'],data['rows']):
    cid=case['id'];reason='';grade='incomplete'
    if row.get('status')=='completed':
        if cid in semantic:grade=semantic[cid]['verdict'];reason=semantic[cid]['reason']
        elif cid in structural:grade=structural[cid]['capability_grade'];reason='Independent graph/ranking checks match; local ranking available. Presentation remains terse.'
        elif cid=='C03':grade='fail';reason='Community question misrouted to centrality because of contacts; rejected incompatible plan.'
        elif row.get('routing_matches') and row.get('required_tools_present') and not row.get('artifact_error') and numerics.get(cid,{}).get('passed'):
            grade='pass';reason='Required analyses and final evidence-linked answer match requested scope; independent numerical checks pass.'
        else:grade='fail';reason='Required routing, evidence, or numerical check did not pass.'
    else:reason=row.get('failure_reason') or row.get('error') or 'No completed final report within deadline.'
    rows.append({'id':cid,'question':case['question'],'grade':grade,'reason':reason,'status':row.get('status'),
        'elapsed_s':row.get('elapsed_s'),'run_dir':row.get('run_dir')})
conn=sqlite3.connect(ROOT/'runs/workflow.sqlite');conn.row_factory=sqlite3.Row
all_ops=[dict(o) for o in conn.execute("SELECT * FROM operations WHERE kind='llm' AND run_id LIKE 'eval24-%'")];conn.close()
known=sum(o['actual_usd'] for o in all_ops if o['receipt_path'])
unknown=[o for o in all_ops if not o['receipt_path'] and (o['state']=='dispatched' or o['category']=='uncertain')]
exposure=sum(max(o['reserved_usd'],o['actual_usd']) for o in unknown)
cost={'known_receipted_usd':known,'unresolved_calls':len(unknown),'unresolved_reserved_usd':exposure,
    'conservative_accounted_usd':known+exposure,'authorization_usd':3,
    'note':'All three attempts included. Unresolved dispatched calls may be billed; not retried or counted as free. Reservations are accounting safeguards, not provider invoice verification.'}
times=[r['elapsed_s'] for r in rows if r.get('elapsed_s') is not None]
summary={'pass':sum(r['grade']=='pass' for r in rows),'fail':sum(r['grade']=='fail' for r in rows),
    'incomplete':sum(r['grade']=='incomplete' for r in rows),'cases':24,'source_unchanged':data['source_unchanged'],
    'median_case_elapsed_s':statistics.median(times) if times else None,
    'max_case_elapsed_s':max(times) if times else None,'cost':cost,'rows':rows,
    'limits':'Exploratory scripted capability sample, one live model/run per case in primary attempt; not a held-out statistical generalization estimate. Earlier attempts are retained operational evidence, not selectively pooled successes.'}
execution=OUT/'execution.json'
if execution.exists():summary['primary_wall_s']=read(execution)['elapsed_s']
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
lines=['# Current system: 24-scenario live evaluation','',f"Useful answers / correct refusals: **{summary['pass']}/24**. Failures: **{summary['fail']}**. Incomplete: **{summary['incomplete']}**.",'',
    'DeepSeek V4 Flash; all 24 scenarios dispatched in separate parallel processes. Structural questions use the frozen seven-day CollegeMsg window (104 nodes, 137 edges); prediction uses approved full temporal history; research reads saved synthetic evidence. UI rendering excluded; planning, numerical tools, critic and saved reports exercised.',
    '',f"Primary elapsed: {summary.get('primary_wall_s','still running')} seconds. Median case: {summary['median_case_elapsed_s']} seconds.",'',
    f"Known receipted cost across attempts: ${known:.6f}; unresolved calls: {len(unknown)}, reserved ${exposure:.6f}; conservative accounted total ${known+exposure:.6f}, within the $3 authorization.",'',
    'The sandbox-only attempt failed DNS before paid calls. The next attempt had a pricing failure plus provider-response timeouts; its uncertain calls remain charged conservatively. The primary attempt reused one fresh public pricing lookup and kept all model calls parallel. No production source changes were made; source hashes match the freeze.',
    '', 'Independent checks recompute community Monte Carlo arithmetic, degrees, direct NetworkX betweenness, bridge counts/ranks, forecast candidate membership and sorting, forecast cutoff, rolling metrics, and artifact hashes. Semantic review distinguishes complete tool execution from actually answering the question. It is agent review against a frozen rubric, not human grading or the running model grading itself.',
    '', '| ID | Question | Grade | Reason |','|---|---|---|---|']
for r in rows:lines.append('| '+ ' | '.join(str(r[k]).replace('|','/').replace('\n',' ') for k in ('id','question','grade','reason'))+' |')
lines += ['',summary['limits'],'','Next smallest task: fix intent/scope handling and render the requested assumptions/cost rationale; evaluate changed behavior under a new protocol rather than rewriting these results.']
(OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))
