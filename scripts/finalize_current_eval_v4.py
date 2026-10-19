"""Record the assistant's semantic review under the pre-execution rubric.

No paid calls or production changes. The original automated audit is preserved.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runs/current-system-eval-v4'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
audit=read(OUT/'audit.json');freeze=read(OUT/'freeze.json')
notes={
 'Q-C1':(True,'Correct bounded null conclusion, effect, uncertainty and sensitivity; no group-truth claim.'),
 'Q-C2':(True,'Both null comparison and uniform 10% removal are answered; sensitivity is distinguished from uncertainty.'),
 'Q-C3':(True,'Correct community test, rather than contact ranking; not_supported does not claim proof of the null.'),
 'Q-C4':(False,'Planner response hit max_tokens=4096 and was truncated. No numerical answer; incomplete.'),
 'Q-N1':(True,'Degree values and local degree_rank table match the graph; graph scope and noncausal status stated.'),
 'Q-N2':(True,'Local betweenness values/ranks and shortest-path explanation provided. Artifact explicitly records approximate=false and sample_sources=104. Generic report text about sampled estimates is a presentation weakness.'),
 'Q-N3':(False,'Question asks for BOTH degree and betweenness stability. ranking_sensitivity.json computes only metric=betweenness; degree stability is absent. Final text does not identify the metric of its Jaccard value.'),
 'Q-B1':(True,'Partition-dependent cross-community ranking available locally and matches graph; descriptive scope.'),
 'Q-B2':(False,'Connector ranking is numerically correct, but the requested explanation of how the score is calculated is omitted. Naming cross-community degree and saying it depends on a partition does not define the neighbour-count formula.'),
 'Q-B3':(True,'Cross-degree ranking sensitivity exists with uniform removal, correct aggregate and mechanism limitations. Local artifact specifies metric, top_k and replicate count.'),
 'Q-R1':(True,'Correct saved synthetic method A success posterior mean and credible interval; no real-data transfer.'),
 'Q-R2':(True,'Saved stop decision, cost, EVSI, net value and rationale are explicit and synthetic.'),
 'Q-R3':(True,'Saved 30-independent-graph calibration evidence and paired Brier bootstrap confidence interval stated with synthetic limits.'),
 'Q-R4':(True,'Synthetic ATE T to Y, independent graph unit, adjustment X and supplied identification assumptions stated; real effects explicitly not identified.'),
 'Q-X1':(True,'Explicitly refuses observational behavioral causality; no numerical tools or unsupported substitute.'),
 'Q-X2':(True,'Explicitly refuses calibrated pair probability and tomorrow horizon; no numerical tools.'),
 'Q-X3':(True,'Explicitly refuses synthetic posterior transfer to real communities.'),
 'Q-X4':(True,'Explicitly refuses causal behavior effect from graph deletion.'),
 'Q-X5':(True,'Explicitly rejects held-out/future information access; no tool execution.'),
 'Q-X6':(True,'Explicitly rejects window fishing and hidden unsuccessful attempts; no tool execution.')}
for cid in ('Q-F1','Q-F2','Q-F3','Q-F4'):
    notes[cid]=(False,'Task, candidate set, cutoff, horizon and rolling numerical metrics are correct, but the final report labels scope:first_window and graph:collegemsg-window while the forecast uses full temporal history. Its boilerplate also claims evidence from two held-out windows of one network despite the displayed five development windows and saved external confirmation. These conflicting factual scope statements fail the frozen scope/correctness criterion. No forecast calculation failure is alleged.')
cases={c['id']:c for c in freeze['cases']}
for row in audit['rows']:
    ok,note=notes[row['id']]
    row['semantic_review']={'pass':ok,'reason':note,'reviewer':'Codex assistant applying frozen rubric; not human review or running-model self-rating'}
    row['grade']='incomplete' if row['id']=='Q-C4' else ('pass' if ok and row.get('automated_grade')=='pass' else 'fail')
    row['category']=cases[row['id']]['expected_family']
summary={k:sum(r['grade']==k for r in audit['rows']) for k in ('pass','fail','incomplete')}
summary.update(total=24,strict_success_percent=100*summary['pass']/24,automated_evidence_pass=23)
audit['summary']=summary
audit['review_method']='Original automated audit retained separately. Semantic review records answer omissions and contradictory factual scope statements using the already frozen correctness/scope criteria. No post-result protocol or production edits, no reruns.'
(OUT/'reviewed_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
groups=[('Community','community'),('Centrality','centrality'),('Bridges','bridge'),('Forecasting','forecast'),('Saved synthetic research','research'),('Unsupported requests','clarify')]
lines=['# Current system evaluation v4','',f"All 24 frozen scenarios were attempted once with the real OpenRouter provider: **{summary['pass']}/24 strict passes ({summary['strict_success_percent']:.1f}%), {summary['fail']} answer-quality failures, {summary['incomplete']} incomplete model response**. No mocks or selective retries.",'',
'| Category | Pass | Fail | Incomplete |','|---|---:|---:|---:|']
for name,group in groups:
    rr=[r for r in audit['rows'] if r['category']==group]
    lines.append('| '+name+' | '+' | '.join(str(sum(r['grade']==g for r in rr)) for g in ('pass','fail','incomplete'))+' |')
acc=audit['accounting'];lat=audit['latency']
lines+=['','## What worked','',
'23/24 scenarios completed with correct linked numerical evidence or justified refusal. The single incomplete scenario exhausted the model output limit while planning. Structural degree, betweenness and cross-community counts were checked independently against NetworkX/raw graph calculations. Community null arithmetic was recomputed. Forecast candidate membership/count, ordering, cutoff and saved historical metric values matched. Manifest hashes and reported-claim links/numbers passed for all 23 completed cases.',
'','## What failed','',
'- Q-C4: planner output truncated at 4096 tokens; no answer. Kept incomplete and never retried.',
'- Q-N3: asked for degree and betweenness stability; only betweenness stability was computed/reported.',
'- Q-B2: correct connector ranking, but no requested explanation of the score formula.',
'- Q-F1–Q-F4: correct forecast task and calculations, but misleading report scope and obsolete evaluation boilerplate. Reports say first_window although forecasts use full history, and two held-out windows although their displayed metrics are five development windows with saved external confirmation.',
'',
'The automated evidence check scored 23/24. The strict answer score is 17/24 because correct calculations alone do not satisfy the frozen completeness and scope requirements. Forecasting therefore scores 0/4 on strict report quality while its numerical evidence checks score 4/4. No accepted behavioral-causal or calibrated individual-probability claims appeared in these cases.',
'','## Execution and spending','',
f"- Four separate workers; batch execution {audit['execution']['elapsed_s']:.2f} seconds; median case {lat['median_s']:.2f}s, p90 {lat['p90_s']:.2f}s, maximum {lat['max_s']:.2f}s.",
f"- Live model: deepseek/deepseek-v4-flash-0731 via OpenRouter. {acc['recorded_llm_operations']} receipted model operations across 18 supported-question attempts. Six unsupported requests were refused by deterministic production guards with zero model calls; these are system refusal checks, not evidence of LLM refusal ability.",
f"- Newly receipted charge: USD {acc['known_receipted_usd']:.8f}; new unresolved reservations: USD {acc['unresolved_reserved_usd']:.8f} ({acc['unresolved_calls']} calls). Receipt files and hashes were verified.",
f"- Project conservative accounted spending including earlier charges/reservations: USD {acc['project_conservative_usd']:.8f}, under the USD 3 ceiling. Historical unresolved charges remain reserved; they were not erased or retried.",
'- Frozen source/protocol/evaluator hashes unchanged during execution. Added only evaluation protocol/harness/review/report artifacts; production code unchanged in this evaluation.',
'','## Limits and next smallest task','',
'This is an exploratory portfolio-system evaluation on reused CollegeMsg data and saved synthetic evidence, not 24 independent graphs, a sealed generalization test, or a new predictive-model benchmark. Normal numerical caches and saved rolling/confirmation results were reused; models were not retrained. UI rendering was excluded; local ranking artifacts were inspected. Semantic review was by this assistant, not a human or independent LLM. Forecast score values were checked for artifact consistency, not independently retrained. Static report prose needs review in addition to checked claim fields.',
'',
'The next smallest fix is to make forecast report scope and evaluation-window prose derive from the actual prediction artifacts. Then address centrality sensitivity for both requested metrics, connector explanations, and planner truncation under a new protocol. This evaluation deliberately makes none of those production changes.',
'','## Per-case review','',
'| Case | Outcome | Review |','|---|---|---|']
for r in audit['rows']:lines.append(f"| {r['id']} | {r['grade']} | {r['semantic_review']['reason']} |")
lines+=['','Artifacts: [frozen protocol](../../protocols/current_system_eval_v4.json), [freeze](freeze.json), [execution](execution.json), [original automated audit](audit.json), [reviewed audit](reviewed_audit.json). Individual case markers link to immutable run directories and their reports.','']
(OUT/'report.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(summary|{'cost_usd':acc['known_receipted_usd'],'elapsed_s':audit['execution']['elapsed_s']},indent=2))
