"""Numerical and report regressions; no model provider is invoked."""
import math
import random
from types import SimpleNamespace

import networkx as nx
import pytest

from blackgrid.analysis.structural import compute
from blackgrid.agent.report import build_report,check_numbers,render_markdown
from blackgrid.agent.roles import flatten

def test_both_stability_metrics_use_the_registered_removals():
    graph=nx.gnp_random_graph(17,.3,seed=7);seed=42
    central=compute('node_centrality',graph,'test',seed,10,{})
    result=compute('ranking_sensitivity',graph,'test',seed,10,{'node_centrality.json':central})
    edges=sorted(graph.edges(),key=lambda e:tuple(sorted(map(str,e))))
    def top(values):
        threshold=sorted(values.values(),reverse=True)[4]
        return {n for n,v in values.items() if v>=threshold}
    for name,measure in [('degree',lambda g:dict(g.degree())),('betweenness',nx.betweenness_centrality)]:
        base=top(measure(graph));overlaps=[]
        for i in range(3):
            reduced=graph.copy()
            reduced.remove_edges_from(random.Random(seed+10000+i).sample(edges,math.floor(.1*len(edges))))
            other=top(measure(reduced));overlaps.append(len(base&other)/len(base|other))
        assert result['summary'][name+'_mean_top_jaccard']==pytest.approx(sum(overlaps)/3)
    assert result['version']=='structural-v2'

def report_inputs(cid):
    forecast=cid.startswith('Q-F')
    inv=SimpleNamespace(family='forecast' if forecast else 'bridge',reported_claims=[],plan_decision=None,
        verdict='supported',tool_calls=[],case_id='example',condition='validated',
        status=SimpleNamespace(value='completed'),failure_reason=None)
    record=SimpleNamespace(scope='first_window',graph_id='structural-context')
    outputs={'link_prediction.json':{'cutoff':123},'prediction_compare.json':{
        'split':'rolling','windows':5,'evidence':'development',
        'confirmation':{'dataset':'external-example','evaluable_origins':5}}} if forecast else {
        'community_bridge.json':{'summary':{'metric':'cross_community_degree'}}}
    return inv,record,outputs

@pytest.mark.parametrize('cid',['Q-F1','Q-F2'])
def test_forecast_report_does_not_inherit_structural_window(cid):
    inv,record,outputs=report_inputs(cid)
    outputs['link_prediction.json'].update(scope='full_observed_history',history_nodes=1899,history_pairs=13838)
    evidence=flatten(outputs)
    report=build_report(inv,evidence,record,'Forecast question','regression','')
    text=render_markdown(report)
    assert 'full_observed_history' in text
    assert 'scope: first_window' not in text
    assert 'two held-out windows' not in text
    assert '5 rolling windows' in text and 'development' in text
    assert not check_numbers(report,evidence)

def test_bridge_report_explains_score():
    inv,record,outputs=report_inputs('Q-B2');evidence=flatten(outputs)
    report=build_report(inv,evidence,record,'Explain connector score','regression','')
    assert "neighbours whose community differs from their own" in render_markdown(report)
    assert not check_numbers(report,evidence)

def test_closed_community_summary_preserves_negative_evidence():
    from blackgrid.workflow.engine import community_summary
    from blackgrid.agent.critic import CriticContext,critique
    outputs={'experiment_report.json':{'verdict':'not_supported','secondary':None,'primary':{'result':{
        'observed_statistic':.3,'null':{'mean':.4},'p_value':.8}}},
        'sensitivity.json':{'removal_fraction':.1,'replicates':20,'agreement_fraction':1.0}}
    ctx=CriticContext(evidence=flatten(outputs),verdict='not_supported',delta_q=-.1,p_value=.8,alpha=.05)
    claims=community_summary(outputs)
    assert claims and all(critique(c,ctx).accepted for c in claims)
    assert any('not_supported' in c['text'] for c in claims)
    assert all('exceeds' not in c['text'] for c in claims)


def test_default_evidence_summary_completes_without_a_writer(tmp_path):
    from collections import Counter
    from tests.test_workflow import Counting,start
    class PlannerOnly(Counting):
        def complete(self,role,*args,**kwargs):
            assert role=='planner', 'Evidence summary must not dispatch an interpretation call'
            return super().complete(role,*args,**kwargs)
    provider=PlannerOnly()
    out=start(tmp_path,provider,None,summary_mode='evidence')
    assert out.outcome.status=='completed'
    assert out.result.verdict=='not_supported'
    assert out.result.reported_claims and all(c.accepted for c in out.result.critic_decisions)
    assert provider.calls==Counter(planner=1)


def test_unknown_summary_policy_fails_before_provider_dispatch(tmp_path):
    from tests.test_workflow import Counting,start
    provider=Counting()
    out=start(tmp_path,provider,None,summary_mode='unrestricted')
    assert out.outcome.status=='failed' and 'summary_mode' in out.outcome.reason
    assert not provider.calls
