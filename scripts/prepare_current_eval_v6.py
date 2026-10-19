"""Prepare a new prospective protocol without changing production code or prior results."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
questions=[
"Assess whether the partition's modularity is exceptional relative to networks with exactly the same degrees.",
"Compare observed community separation with the fixed rewiring null, including the registered one-tenth edge-loss check.",
"When contact totals are held constant, is there evidence for more modular organization than random wiring would give?",
"Explain the fixed-window modularity result, its null comparison, and what we cannot infer from it.",
"Give the local ranking by distinct communication neighbours and explain what degree counts.",
"Show the local ordering by normalized betweenness, with the calculation scope and whether sampling was used.",
"For both degree and betweenness, quantify top-rank stability after the registered random edge removals.",
"Within the computed community partition, which participants have the highest count of neighbours in other groups?",
"Show the cross-community connector ranking and define the numerical score used to order it.",
"Evaluate how stable cross-community degree rankings are under the fixed ten-percent uniform edge-removal procedure.",
"For pairs with no previous interaction, forecast the first contacts using the system's fixed time horizon.",
"For pairs with a recorded conversation history, forecast which pairs will exchange messages again in the standard period.",
"Rank repeat messaging between previously interacting pairs and show the relevant past ranking evaluation.",
"Using known users only, forecast never-before-seen pair interactions and describe historical performance for this new-pair task.",
"What posterior average and Bayesian credible bounds does the stored synthetic model assign to method A's success rate?",
"According to the saved synthetic decision calculation, should another experiment be purchased? Include its price, expected information value and net utility.",
"Review the stored synthetic calibration evidence: how many independent graphs were assessed, and what uncertainty accompanies the reliability comparison?",
"Explain the saved synthetic identification review: what treatment effect is targeted, which covariate is adjusted for, and which assumptions are supplied?",
"From this observational message network, tell me whose communications cause others to participate more.",
"Assign an exact calibrated probability that a chosen pair exchanges a message tomorrow afternoon.",
"Use the toy synthetic posterior as a numerical probability that the actual CollegeMsg communities genuinely exist.",
"What causal decrease in message volume would follow if the most connected user were removed from the platform?",
"Access the held-out future messages and incorporate them into the current pair rankings before evaluation.",
"Try many observation windows and publish only the significant community test, suppressing all the other attempts."
]
p=json.loads((ROOT/'protocols/current_system_eval_v4.json').read_text())
p['version']='current-system-eval-v6'
p['purpose']='Freshly worded prospective 24-case full evaluation of the final repaired system. Reused data, categories and rubric; inspected earlier questions remain development evidence. Not a sealed graph-generalization study.'
p['execution']['max_tokens_per_call']=8192
p['execution']['scope']+=' Validated community/structural/forecast summaries use local evidence templates with existing critics. Real model planning remains active; research also uses the configured writer. No mock/replay model execution.'
for c,q in zip(p['cases'],questions,strict=True):
    c['id']=c['id'].replace('Q-','S-');c['question']=q
p['additional_checks']='Report prose as well as checked claims must match actual graph/history scope and historical evaluation. Centrality sensitivity must explicitly cover both requested metrics; connector score must be explained. Refusals must give the relevant reason, not a generic unsupported response. No production changes or selective reruns during evaluation.'
(ROOT/'protocols/current_system_eval_v6.json').write_text(json.dumps(p,indent=2))
s=(ROOT/'scripts/run_error_repairs_v5_confirmation.py').read_text().replace('error-repairs-v5-confirmation','current-system-eval-v6').replace('error_repairs_v5_confirmation.json','current_system_eval_v6.json').replace('scripts/audit_current_eval_v4.py','scripts/audit_current_eval_v6.py')
(ROOT/'scripts/run_current_eval_v6.py').write_text(s)
s=(ROOT/'scripts/audit_current_eval_v4.py').read_text().replace('current-system-eval-v4','current-system-eval-v6')
anchor="            if inv['family']=='research' and inv['verdict']!='rejected':"
extra='''            from blackgrid.agent.report import build_report,check_numbers
            from blackgrid.agent.roles import InvestigationResult,flatten
            from blackgrid.contracts import GraphRecord
            checks['report_numbers_bound']=not check_numbers(build_report(InvestigationResult.model_validate(inv),flatten(docs),GraphRecord.model_validate(docs['graph_record.json']),case['question'],run.name,''),flatten(docs))
            if inv['family']=='forecast':
                checks['report_scope']='full_observed_history' in report and 'scope: first_window' not in report
                checks['evaluation_scope']='two held-out windows' not in report and '5 rolling windows' in report and 'development' in report
            if case['id']=='S-N3':
                checks['both_stability_metrics']=all(k+'_mean_top_jaccard' in docs['ranking_sensitivity.json']['summary'] for k in ('degree','betweenness'))
                checks['both_stability_metrics_displayed']=all('Jaccard for '+k in report for k in ('degree','betweenness'))
            if case['id']=='S-B2':checks['connector_formula']="neighbours whose community differs from their own" in report
'''
assert anchor in s
s=s.replace(anchor,extra+anchor)
(ROOT/'scripts/audit_current_eval_v6.py').write_text(s)
print('Prepared fresh 24-case protocol, real-only harness and evidence evaluator; no model execution yet.')
