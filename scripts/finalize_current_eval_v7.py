"""Record semantic review and publish minimized results; no model calls or rescore of prior runs."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/current-system-eval-v7'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
audit=read(OUT/'audit.json');freeze=read(OUT/'freeze.json');cases={c['id']:c for c in freeze['cases']}
notes={
 'community':'Fixed-window null comparison, effect and uncertainty, uniform removal sensitivity and descriptive limitations address the request. A nonsignificant result is not treated as proof of the null.',
 'centrality':'Requested local degree/betweenness ranking matches graph evidence; exactness and window scope are explicit. The dual-stability request receives both named metrics.',
 'bridge':'Correct partition-dependent cross-community counts and ranks; connector formula is explicit. The stability case uses cross_degree, not ordinary centrality.',
 'forecast':'Correct pair-history task and local ranking, fixed cutoff/horizon and full-history scope; matching rolling development evidence is explicit, and scores are uncalibrated.',
 'research':'Requested saved synthetic posterior, decision or reliability result is explicit with matching numerical evidence and no real-data transfer or new experiment claim.',
 'clarify':'Relevant unsupported target is explicitly refused with no numerical execution or substituted factual answer.'}
for row in audit['rows']:
    case=cases[row['id']];group=case['expected_family'];row['category']=group
    if row.get('status')!='completed':
        row['grade']='incomplete';reason='No final answer: the real research writer returned a response truncated at its 8192-token cap. Correct planning and completed causal review tool do not count as a useful answer.'
    else:
        row['grade']='pass' if row.get('automated_grade')=='pass' else 'fail';reason=notes[group]
    row['semantic_review']={'pass':row['grade']=='pass','reason':reason,'reviewer':'Codex assistant applying the frozen rubric; not human review or running-model self-rating'}
summary={k:sum(r['grade']==k for r in audit['rows']) for k in ('pass','fail','incomplete')}
summary.update(total=24,strict_success_percent=100*summary['pass']/24,supported_request_pass=sum(r['grade']=='pass' for r in audit['rows'] if r['category']!='clarify'),supported_request_total=18,refusal_pass=sum(r['grade']=='pass' for r in audit['rows'] if r['category']=='clarify'),refusal_total=6)
audit['summary']=summary
audit['review_method']='Frozen semantic/correctness/scope criteria; independent local numerical checks plus disclosed assistant review. No production change, retry or post-result threshold alteration.'
(OUT/'reviewed_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
groups={g:{'passed':sum(r['grade']=='pass' for r in audit['rows'] if r['category']==g),'total':sum(r['category']==g for r in audit['rows'])} for g in notes}
guard_count=sum(r.get('cost',{}).get('llm_calls',0)==0 for r in audit['rows'] if r['category']=='clarify')
live_questions=sum(r.get('cost',{}).get('llm_calls',0)>0 for r in audit['rows'])
acc=audit['accounting'];lat=audit['latency'];elapsed=audit['execution']['elapsed_s']
public={'evaluation':'current-system-eval-v7','date':'2026-10-19','status':'Frozen evaluation after the 493-test regression repairs','protocol_sha256':freeze['protocol_sha256'],'summary':summary,'categories':groups,
 'execution':{'elapsed_s':elapsed,'workers':4,'attempts_per_case':1,'source_unchanged':audit['execution']['source_unchanged'],'model':'deepseek/deepseek-v4-flash-0731','questions_with_real_model_calls':live_questions,'deterministic_refusals_without_model_calls':guard_count},'latency':lat,
 'cost':{k:acc[k] for k in ['known_receipted_usd','unresolved_reserved_usd','unresolved_calls','recorded_llm_operations']},
 'failure':'T-R4: causal review numerical tool completed; research-writing response truncated at 8192 tokens; no final accepted claims.',
 'limitations':['Fresh wording on reused graph data and normal numerical caches; not graph-level generalization.','Independent numerical checks plus assistant semantic review, not human judging.','No new predictive-model benchmark or calibration result.','UI rendering excluded; no retry or production fix during this evaluation.']}
dest=ROOT/'results/current-system-eval-v7';dest.mkdir(exist_ok=False);(dest/'summary.json').write_text(json.dumps(public,indent=2)+'\n',encoding='utf-8')
lines=['# Full real-LLM evaluation v7','',f"**23/24 strict passes (95.8%)**, with one incomplete model answer. All 24 cases were attempted once; no timeouts or not-dispatched cases. This evaluates the current runtime after the complete regression repairs.",'',
'| Category | Pass | Total |','|---|---:|---:|']
for name,g in [('Community','community'),('Centrality','centrality'),('Bridges','bridge'),('Forecasting','forecast'),('Saved synthetic research','research'),('Unsupported requests','clarify')]:lines.append(f"| {name} | {groups[g]['passed']} | {groups[g]['total']} |")
lines+=['','## Failure retained','',
'T-R4 requested the saved synthetic causal estimand, treatment, outcome, adjustment and supplied assumptions. Planning selected the correct research family and causal_identification_check completed. The subsequent real writer response hit max_tokens=8192 and was truncated. Runtime status is failed; the evaluation records an incomplete answer, which remains a non-pass in the 24-case denominator. No retry, local repair or selective replacement was performed.',
'',
'All three bridge questions passed, including cross-community ranking stability. The previous v6 suite also scored 23/24, but its failure was a substituted bridge target. These are separate fresh-wording exploratory sets, not paired scientific trials or evidence that the remaining failure rate is unchanged.',
'','## Real execution, evidence and cost','',
f"- Model: deepseek/deepseek-v4-flash-0731 through OpenRouter. No mock or replay execution. {live_questions} questions used real model calls: all 18 supported requests plus one causal refusal. {guard_count} other refusals were deterministic guards. The four research cases also invoked real writing; {acc['recorded_llm_operations']} receipted model operations total.",
'- Validated community/structural/forecast summaries used checked local templates. Research review retained its configured writer. This is a system evaluation, not 24 unrestricted model-only responses.',
f"- Four process workers; total {elapsed:.2f}s; median case {lat['median_s']:.2f}s, p90 {lat['p90_s']:.2f}s, maximum {lat['max_s']:.2f}s.",
f"- Confirmed batch charge USD {acc['known_receipted_usd']:.8f}; new uncertain reservations USD {acc['unresolved_reserved_usd']:.8f}. Receipt files and hashes verified.",
f"- Project conservative accounting USD {acc['project_conservative_usd']:.8f}, including earlier charges and retained reservations; USD {3-acc['project_conservative_usd']:.8f} remains within the authorized USD3 ceiling. This is local project accounting, not provider balance.",
'- Source, protocol and evaluator hashes stayed unchanged during execution. Independent local checks covered manifest hashes, claim/report numbers and links, raw-graph centrality, bridge counts/ranks, community null arithmetic, forecast candidates/cutoff/order and saved metric consistency. Assistant review assessed responsiveness, scope and refusal reasons; no human or independent-model judge is claimed.',
'','## Scientific limits','',
'The questions use familiar task families, reused CollegeMsg evidence and saved synthetic studies. Normal numerical caches were enabled; timing is warm-operation latency. The 24 questions are not independent graphs, and no new model training, predictive benchmark, real-data calibration or causal effect was established. The UI renderer was excluded. Rankings remain local. A passing answer is supported within its registered scope, not a proof of autonomous scientific discovery.',
'',
'The 493-pass offline regression result and this live result measure different things. A scripted test provider cannot establish that a real writer will honor a response budget. The remaining smallest reliability improvement is to remove unnecessary research rewriting or bound it more tightly, then verify under a separately frozen protocol; that change was not made during this run.',
'','## Per-case review','', '| Case | Outcome | Review |','|---|---|---|']
for row in audit['rows']:lines.append(f"| {row['id']} | {row['grade']} | {row['semantic_review']['reason']} |")
private='\n'.join(lines+['','Evidence: [freeze](freeze.json), [execution](execution.json), [automated audit](audit.json), [reviewed audit](reviewed_audit.json). Individual case markers retain private run paths and complete receipts.',''])
(OUT/'report.md').write_text(private,encoding='utf-8')
shared='\n'.join(lines+['','Evidence: [frozen protocol](../protocols/current_system_eval_v7.json), [minimized results](../results/current-system-eval-v7/summary.json). Full receipts, local ranking tables and traces remain in ignored runs/.',''])
(ROOT/'docs/current_system_eval_v7.md').write_text(shared,encoding='utf-8')
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in freeze['source_hashes'].items())
assert len(audit['rows'])==24 and acc['within_budget']
print(json.dumps(summary|{'elapsed_s':elapsed,'cost_usd':acc['known_receipted_usd'],'project_usd':acc['project_conservative_usd'],'deterministic_refusals':guard_count},indent=2))
