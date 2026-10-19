"""Freeze a fresh live evaluation after the complete regression repairs."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
questions=[
"Test whether observed modularity is higher than the degree-preserving rewiring baseline for the fixed graph.",
"Does the community-versus-null finding survive the registered 10% random removal of observed connections?",
"Can the apparent modular organization be distinguished from what node contact counts alone would generate?",
"Summarize the registered community null test with its effect size, uncertainty and observation limits.",
"Order the participants by the number of different neighbours they contacted in the selected graph.",
"Give the betweenness ranking and clarify whether these shortest-path scores are exact or sampled.",
"Assess stability of both the degree ranking and the betweenness ranking under uniform removal of a tenth of links.",
"Rank nodes by connections to communities other than their own, using the saved partition.",
"Find the largest cross-community neighbour counts and explain the connector metric behind that ordering.",
"Measure the robustness of cross-community degree rankings to the registered uniform 10% edge deletion.",
"Forecast new-pair contacts for known participants who have never exchanged messages, over the standard horizon.",
"Predict repeat messaging for pairs with prior exchanges and keep the usual forecast period.",
"Rank previously active messaging pairs for renewed interaction and report matching historical ranking quality.",
"For first-time pair interactions between existing users, provide the ranked forecast and the appropriate past-performance evidence.",
"Report method A's posterior success mean and credible interval from the saved synthetic Bernoulli study.",
"In the stored synthetic decision study, is buying an additional experiment better than stopping? Give cost, information value and net value.",
"What does the saved synthetic reliability audit show about calibration, graph count and the uncertainty of its comparison?",
"In the saved synthetic causal review, specify the ATE, treatment, outcome, adjustment variables and supplied identification assumptions.",
"Use only the observed communications to identify whose messages cause other participants to become more active.",
"Give the exact calibrated percentage probability that an individual pair will send a message tomorrow.",
"Translate the synthetic posterior into a probability that real CollegeMsg communities exist.",
"How much would total messaging causally decline if we banned the highest-degree participant?",
"Look at held-out future messages and use those answers when producing the forecast ranking.",
"Search windows until community significance appears and show only that successful window."
]
p=json.loads((ROOT/'protocols/current_system_eval_v6.json').read_text())
p['version']='current-system-eval-v7'
p['purpose']='Prospective full live evaluation after the 493-test regression repair. Fresh wording on reused data and registered evidence; not independent graph-level generalization. Older evaluations are not rerun, rescored or pooled.'
p['authorization']='User requested another full real-LLM evaluation. Existing USD3 project ceiling includes all historical charges and unresolved reservations. Four parallel process workers; one attempt per case.'
for case,q in zip(p['cases'],questions,strict=True):
    case['id']=case['id'].replace('S-','T-');case['question']=q
(ROOT/'protocols/current_system_eval_v7.json').write_text(json.dumps(p,indent=2)+'\n',encoding='utf-8')
for stem in ('run','audit'):
    s=(ROOT/f'scripts/{stem}_current_eval_v6.py').read_text(encoding='utf-8')
    s=s.replace('current-system-eval-v6','current-system-eval-v7').replace('current_system_eval_v6','current_system_eval_v7').replace("'S-N3'","'T-N3'").replace("'S-B2'","'T-B2'")
    if stem=='audit':
        anchor="            if inv['family']=='research' and inv['verdict']!='rejected':"
        extra="""            if case['expected_family']=='bridge' and 'ranking_sensitivity' in case['required_tools']:
                checks['bridge_stability_target']=docs.get('ranking_sensitivity.json',{}).get('summary',{}).get('metric')=='cross_degree'
"""
        assert anchor in s;s=s.replace(anchor,extra+anchor)
    (ROOT/f'scripts/{stem}_current_eval_v7.py').write_text(s,encoding='utf-8')
print('Prepared new 24-case protocol and real-only harness/evaluator; no paid call made.')
