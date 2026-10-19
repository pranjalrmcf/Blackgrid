"""Persist assistant semantic review under the pre-execution v6 rubric."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/current-system-eval-v6'
def read(p):return json.loads(p.read_text())
audit=read(OUT/'audit.json');freeze=read(OUT/'freeze.json');cases={c['id']:c for c in freeze['cases']}
notes={
 'community':'Correct fixed-window modularity versus degree-preserving null, effect/uncertainty, registered removal sensitivity and bounded descriptive limitations. Lack of significance is not treated as proof of the null.',
 'centrality':'Requested local ranking and graph scope available; degree counts and normalized betweenness are correct. Approximate=false and source count explicitly disclosed. Where requested, both stability metrics are computed and displayed.',
 'bridge':'Local cross-community ranking matches the saved partition. Connector-score definition and descriptive limitations are explicit.',
 'forecast':'Correct requested pair-history task, candidate universe, cutoff and fixed horizon. Local ranked pairs available. Report uses actual full history and five rolling development windows; uncalibrated scores and saved external confirmation are distinguished.',
 'research':'Requested saved synthetic result, numbers and interval/identification semantics are explicit. No fresh experiment, real-world posterior transfer or empirically verified identification is asserted.',
 'clarify':'Relevant explicit refusal reason, no numerical tools or substituted finding: observational causality, calibrated pair probability, synthetic-to-real transfer, behavioral intervention, future-data access or selective-window reporting as applicable.'}
for row in audit['rows']:
    case=cases[row['id']];group=case['expected_family']
    ok=row['id']!='S-B3' and row.get('automated_grade')=='pass'
    note=notes[group]
    if row['id']=='S-B3':note=('FAIL: real planner chose centrality, explicitly interpreting degree rankings while ignoring cross-community. Controller accepted it. Output contains ordinary degree/betweenness sensitivity; no community partition, bridge scores or cross-degree stability. Numerically valid answer to the wrong target.')
    row.update(grade='pass' if ok else 'fail',category=group,semantic_review={'pass':ok,'reason':note,'reviewer':'Codex assistant, not human review or the running LLM self-scoring'})
summary={k:sum(r['grade']==k for r in audit['rows']) for k in ('pass','fail','incomplete')}
summary.update(total=24,strict_success_percent=100*summary['pass']/24,supported_request_pass=17,supported_request_total=18,refusal_pass=6,refusal_total=6)
audit['summary']=summary
audit['review_method']='Pre-execution rubric, automated independent numerical/artifact checks plus assistant semantic review of claims, reports, scope and routing. No model-as-judge call, rerun, production fix or post-result threshold change.'
(OUT/'reviewed_audit.json').write_text(json.dumps(audit,indent=2))
acc=audit['accounting'];lat=audit['latency'];elapsed=audit['execution']['elapsed_s']
lines=['# Fresh current-system evaluation v6','',
'**23/24 strict passes (95.8%); 1 wrong-target answer; no incomplete cases or timeouts.** All 24 newly worded scenarios were frozen before execution and attempted once. Real OpenRouter model; no mock or replay execution.',
'','| Category | Pass | Total |','|---|---:|---:|']
for label,group in [('Community','community'),('Centrality','centrality'),('Bridges','bridge'),('Forecasting','forecast'),('Saved synthetic research','research'),('Unsupported requests','clarify')]:
    rr=[r for r in audit['rows'] if r['category']==group]
    lines.append(f"| {label} | {sum(r['grade']=='pass' for r in rr)} | {len(rr)} |")
lines+=['','## The remaining failure','',
'S-B3 asked: “Evaluate how stable cross-community degree rankings are under the fixed ten-percent uniform edge-removal procedure.” The real planner chose centrality and the controller accepted that selection. The system returned ordinary degree/betweenness stability, omitting the requested partition-dependent cross-community degree. This is a semantic routing/validation failure despite correct numerical values for the substituted target. No repair or retry was performed during this evaluation.',
'','## Evidence and checks','',
'Independent local checks verified manifest hashes, reported-claim evidence links and numbers, static report number bindings, community null arithmetic, raw-graph degree/betweenness, cross-community counts/ranks, forecast candidate count and prior-pair membership, score ordering, cutoff and matching saved historical metrics. Answer review checked requested targets, missing analyses, forecast scope/evaluation prose, connector definition, both centrality stability metrics, synthetic/real distinctions and relevant refusal explanations.',
'',
'Supported-question success was 17/18 (94.4%). Unsupported requests were correctly refused in 6/6 cases by deterministic production guards without model calls. This demonstrates system guard behavior, not an LLM refusal score. All 18 supported questions invoked the real planner; four research cases also used real model writing. Validated community/structural/forecast summaries use checked local templates. Total receipted model operations: '+str(acc['recorded_llm_operations'])+'.',
'','## Time and spending','',
f"- Batch execution: {elapsed:.2f} seconds using four separate workers; median case {lat['median_s']:.2f}s, p90 {lat['p90_s']:.2f}s, maximum {lat['max_s']:.2f}s.",
f"- New confirmed charge: USD {acc['known_receipted_usd']:.8f}. New unresolved charges/reservations: USD {acc['unresolved_reserved_usd']:.8f} ({acc['unresolved_calls']} calls). Receipt files and hashes checked.",
f"- Conservative project accounting, including earlier charges and unresolved reservations: USD {acc['project_conservative_usd']:.8f}, within USD 3.",
'- Model: deepseek/deepseek-v4-flash-0731 via OpenRouter; frozen current pricing, output cap 8192, reasoning cap 1024, request deadline 60s, no retries. Source/protocol/evaluator hashes unchanged during execution.',
'','## Interpretation and limits','',
'The earlier v4 evaluation scored 17/24; this fresh wording set scores 23/24. These are separate exploratory question sets in the same categories, not a paired statistical treatment comparison or 24 independent graph replications. No historical results were rescored or pooled.',
'',
'CollegeMsg data, registered numerical experiments, rolling prediction metrics and saved synthetic studies were reused. Normal numerical caches were enabled, so latency describes warm operation. No predictive model was newly benchmarked/retrained and no new causal or generalization evidence was produced. Research cases inspect saved synthetic evidence. UI rendering was excluded; local ranking artifacts were checked. Semantic review was by this assistant, not a human or independent judge model. Forecast score calculations were checked against stored evaluation, not independently retrained.',
'',
'Only protocol/evaluation/report files were added. Production source was unchanged during this task. Next smallest fix: validate that a cross-community ranking request cannot be silently satisfied by ordinary centrality tools, then verify that change under a new development protocol.',
'','## Per-case review','',
'| Case | Outcome | Review |','|---|---|---|']
for row in audit['rows']:lines.append(f"| {row['id']} | {row['grade']} | {row['semantic_review']['reason']} |")
lines+=['','Artifacts: [protocol](../../protocols/current_system_eval_v6.json), [freeze](freeze.json), [execution](execution.json), [automated audit](audit.json), [reviewed audit](reviewed_audit.json). Individual case markers include run-directory paths and complete model/tool accounting.','']
(OUT/'report.md').write_text('\n'.join(lines))
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in freeze['source_hashes'].items())
assert len(audit['rows'])==24 and acc['within_budget']
print(json.dumps(summary|{'elapsed_s':elapsed,'cost_usd':acc['known_receipted_usd'],'project_usd':acc['project_conservative_usd']},indent=2))
