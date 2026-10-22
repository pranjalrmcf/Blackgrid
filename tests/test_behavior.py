"""Scientific invariants for sprint08_behavior_v1; no paid calls or real labels."""
import hashlib
import json
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from blackgrid.analysis.behavior import BehaviorTools, FEATURES, TOOLS, public_output
from blackgrid.agent.inquiry import family, requirements, safe_outputs, validate_structural
from blackgrid.agent.roles import InvestigationInput
from blackgrid.agent.providers import MockProvider
from blackgrid.agent.tools import ToolRejected, parse_request
from blackgrid.cli import load_config
from blackgrid.data.collegemsg import project, build_bounded_graph
from blackgrid.workflow.runner import run_investigation


def tools(events, end=70):
    return BehaviorTools(events, project([e for e in events if 0 <= e[2] < end]), 0, end)


def varied_events():
    return [(i, (i + 1) % 30, (i * 2 + j) % 70)
            for i in range(30) for j in range(1 + i % 7)] + [(0, 1, 20)] * 500


def test_hand_calculated_features_repeats_reciprocity_and_self_exclusion():
    rows = tools([(1, 2, 0), (1, 2, 0), (2, 1, 10), (2, 3, 69), (4, 4, 20)]).call(TOOLS[0])
    by_node = {r['node']: r for r in rows['rows']}
    expected = [np.log(3), np.log(2), np.log(2), np.log(2), 2/7, 1, 2/3, 2/3]
    assert [by_node[1][f] for f in FEATURES] == pytest.approx(expected)
    assert all(by_node[4][f] == 0 for f in FEATURES)
    assert rows['summary']['excluded_self_events'] == 1
    assert rows['summary']['events'] == 5


def test_future_events_and_input_order_cannot_change_analysis():
    events = varied_events()
    a = tools(events)
    b = tools(list(reversed(events)) + [(99999, 11111, 70), (11111, 99999, 1000)])
    for name in TOOLS:
        assert a.call(name) == b.call(name)


def test_similarity_matches_independent_cosine_and_excludes_self_and_zero_profiles():
    events = [(1, 2, 0), (3, 4, 0), (5, 5, 0)]
    service = tools(events)
    result = service.call('behavior_similarity')
    rows = result['rows']
    assert all(r['node'] != r['neighbor'] and 5 not in (r['node'], r['neighbor']) for r in rows)
    assert next(r for r in rows if r['node'] == 1)['neighbor'] == 3
    x = {r['node']: np.array([r[f] for f in FEATURES]) for r in service.call(TOOLS[0])['rows']}
    for row in rows:
        a, b = x[row['node']], x[row['neighbor']]
        assert row['cosine'] == pytest.approx(float(sum(a*b) / np.sqrt(sum(a*a)*sum(b*b))))


@pytest.mark.parametrize('name', TOOLS[1:])
def test_empty_and_self_only_inputs_abstain(name):
    assert tools([]).call(name)['verdict'] == 'abstain'
    assert tools([(1, 1, 0)]).call(name)['verdict'] == 'abstain'


def test_clustering_population_partition_and_scaling():
    service = tools(varied_events())
    result = service.call('behavior_clustering')
    assert result['verdict'] == 'supported'
    assert sum(r['size'] for r in result['summary']['cluster_profiles']) == 30
    assert len(result['rows']) == 30
    assert set(r['cluster'] for r in result['rows']) == {0, 1, 2}
    assert -1 <= result['summary']['silhouette'] <= 1
    assert np.asarray(result['scaling']['mean']) == pytest.approx(service.x.mean(axis=0))


def test_anomaly_rule_agrees_with_independent_robust_calculation():
    service = tools(varied_events())
    result = service.call('behavior_anomalies')
    x = service.x
    med = np.median(x, axis=0)
    mad = np.array([np.median(abs(x[:, j] - med[j])) for j in range(8)])
    expected = abs(x-med) / np.maximum(1.4826*mad, [1, 1, 1, 1, .1, .1, .1, .1])
    by_node = {r['node']: r for r in result['rows']}
    for i, node in enumerate(service.nodes):
        assert by_node[node]['score'] == pytest.approx(max(expected[i]))
        assert by_node[node]['candidate'] == bool(max(expected[i]) >= 3.5)
    assert result['summary']['candidates'] > 0  # known extreme repeated-event fixture
    assert result['summary']['candidate_overlap'] <= result['summary']['candidates']


def test_identical_population_does_not_manufacture_clusters_or_anomalies():
    service = tools([(i, (i+1) % 30, 0) for i in range(30)])
    assert service.call('behavior_anomalies')['verdict'] == 'abstain'
    assert service.call('behavior_clustering')['verdict'] == 'abstain'


def test_graph_mismatch_caps_invalid_window_and_deadline():
    with pytest.raises(ValueError, match='projection'):
        BehaviorTools([(1, 2, 0)], nx.empty_graph(3), 0, 70)
    with pytest.raises(ValueError, match='1000'):
        BehaviorTools([], nx.empty_graph(1001), 0, 70)
    with pytest.raises(ValueError, match='window'):
        BehaviorTools([], nx.Graph(), 70, 0)
    service = tools(varied_events())
    service.deadline = 0
    with pytest.raises(ValueError, match='deadline'):
        service.call('behavior_clustering')


@pytest.mark.parametrize('question,target', [
    ('Find behavioral clusters', 'behavior_clustering'),
    ('Find similar activity profiles', 'behavior_similarity'),
    ('Find anomalous messaging behavior', 'behavior_anomalies'),
])
def test_routing_and_controller_prerequisites(question, target):
    request = {'family': 'auto'}
    assert family(question, request) == 'behavior'
    assert set(requirements(question, request)) == {'behavior_features', target}
    allowed, calls, _ = validate_structural(question, request, {'decision': 'run', 'tool_calls': [{'tool': target}]})
    assert allowed and [c['tool'] for c in calls] == ['behavior_features', target]


def test_behavior_plan_refuses_parameter_changes_duplicates_and_mixed_families():
    for calls in ([{'tool': 'behavior_clustering', 'args': {'k': 10}}],
                  [{'tool': 'behavior_similarity'}] * 2,
                  [{'tool': 'node_centrality'}]):
        assert not validate_structural('Find behavioral clusters', {'family': 'auto'},
                                       {'decision': 'run', 'tool_calls': calls})[0]
    with pytest.raises(ToolRejected):
        parse_request({'tool': 'behavior_anomalies', 'args': {'cutoff': 0}})
    assert family('Which anomalous users cause behavior changes?', {'family': 'auto'}) == 'clarify'


def test_public_payload_uses_allowlist_and_no_node_identifiers():
    service = tools(varied_events())
    for name in TOOLS:
        raw = service.call(name) | {'future_private_field': {'node': 987654321}}
        public = safe_outputs({name+'.json': raw})[name+'.json']
        assert public == public_output(raw)
        assert 'rows' not in public and 'future_private_field' not in public
        assert '"node":' not in json.dumps(public) and '"neighbor":' not in json.dumps(public)


@pytest.mark.parametrize('question', ['Find behavioral clusters', 'Find similar activity profiles',
                                     'Find anomalous messaging behavior',
                                     'Find behavioral clusters, similarity and anomalies'])
def test_complete_workflow_uses_checksum_verified_events_and_local_artifacts(tmp_path, question):
    raw = '\n'.join(' '.join(map(str, event)) for event in varied_events()).encode()
    (tmp_path / 'events.txt').write_bytes(raw)
    config = load_config(Path('configs/collegemsg_sprint01.json'))
    config = config.model_copy(update={'dataset': config.dataset.model_copy(update={
        'path': 'events.txt', 'sha256': hashlib.sha256(raw).hexdigest()}),
        'question': question, 'investigation_family': 'auto'})
    built = build_bounded_graph(tmp_path, config.dataset, config.window)
    inp = InvestigationInput(case_id=built.record.graph_id, question=question, request={'family': 'auto'},
                             graph=built.graph, record=built.record, spec=config.experiment)
    out = run_investigation(inp, config, MockProvider(), tmp_path / 'runs', cache_dir=None,
                            input_ref={'kind': 'collegemsg', 'data_root': str(tmp_path)})
    inv = json.loads((out.run_dir / 'investigation.json').read_text())
    assert inv['family'] == 'behavior' and inv['status'] == 'completed', inv.get('failure_reason')
    assert inv['reported_claims'] and all(d['accepted'] for d in inv['critic_decisions'])
    manifest = json.loads((out.run_dir / 'manifest.json').read_text())
    assert manifest['status'] == 'completed', manifest.get('failure_reason')
    assert all((name+'.json') in manifest['artifacts'] for name in requirements(question, {'family': 'auto'}))
    trace = (out.run_dir / 'llm_trace.jsonl').read_text()
    assert '"node":' not in trace and '"neighbor":' not in trace
    report = (out.run_dir / 'report.md').read_text(encoding='utf-8')
    assert 'behavioral investigation' in report and 'Robust-deviation' in report
    for name in requirements(question, {'family': 'auto'}):
        assert (out.run_dir / (name+'.json')).exists()
    if 'clusters, similarity' in question:
        anomalies = json.loads((out.run_dir / 'behavior_anomalies.json').read_text())
        comparison = anomalies['summary']['cluster_comparison'].values()
        assert sum(r['size'] for r in comparison) == 30
        assert sum(r['candidates'] for r in comparison) == anomalies['summary']['candidates']
        assert 'Behavioral cluster 0 contains' in report
        assert all('cluster' in r for r in anomalies['rows'])


def test_cluster_comparison_known_counts_zero_profiles_and_privacy():
    from blackgrid.analysis.behavior import compare_clusters
    clustering = {'snapshot_sha256': 'same', 'rows': [
        {'node': n, 'cluster': k} for n, k in ((1, 0), (2, 0), (3, 1), (4, 1), (5, 2), (6, None))]}
    anomaly = {'snapshot_sha256': 'same', 'summary': {}, 'rows': [
        {'node': n, 'candidate': n in (1, 3, 4), 'count_baseline_candidate': n == 4} for n in range(1, 6)]}
    joined = compare_clusters(clustering, anomaly)
    assert list(joined['summary']['cluster_comparison'].values()) == [
        dict(cluster=0, size=2, candidates=1, count_baseline_candidates=0, candidate_fraction=.5, count_baseline_fraction=0),
        dict(cluster=1, size=2, candidates=2, count_baseline_candidates=1, candidate_fraction=1, count_baseline_fraction=.5),
        dict(cluster=2, size=1, candidates=0, count_baseline_candidates=0, candidate_fraction=0, count_baseline_fraction=0)]
    assert [r['cluster'] for r in joined['rows']] == [0, 0, 1, 1, 2]
    assert '"node"' not in json.dumps(public_output(joined))
    assert 'cluster' not in anomaly['rows'][0]  # preserve source receipts
    with pytest.raises(ValueError, match='snapshots'):
        compare_clusters(clustering, anomaly | {'snapshot_sha256': 'different'})
    with pytest.raises(ValueError, match='populations'):
        compare_clusters(clustering, anomaly | {'rows': anomaly['rows'][:-1]})
    assert compare_clusters(clustering | {'verdict': 'abstain'}, anomaly) is anomaly


@pytest.mark.parametrize('cid', ['C1', 'C4', 'C5', 'S1', 'S5', 'A4', 'A5'])
def test_exposed_implicit_requests_keep_the_narrow_validated_plan(cid):
    # Prior evaluated cases are now explicit regression fixtures, not fresh validation questions.
    protocol = json.loads(Path('protocols/sprint08_system_eval_v1.json').read_text())
    case = next(c for c in protocol['cases'] if c['id'] == cid)
    allowed, calls, _ = validate_structural(case['question'], {'family': 'behavior'}, {
        'decision': 'run', 'tool_calls': [{'tool': name, 'args': {}} for name in case['required_tools']]})
    assert allowed
    assert {c['tool'] for c in calls} == set(case['required_tools'])


def test_implicit_feature_only_plan_cannot_masquerade_as_complete_analysis():
    assert not validate_structural('Segment activity patterns', {'family': 'behavior'}, {
        'decision': 'run', 'tool_calls': [{'tool': 'behavior_features', 'args': {}}]})[0]


def test_implicit_planned_analysis_is_a_required_completion_obligation(tmp_path, monkeypatch):
    import blackgrid.workflow.engine as engine
    raw = '\n'.join(' '.join(map(str, event)) for event in varied_events()).encode()
    (tmp_path / 'events.txt').write_bytes(raw)
    config = load_config(Path('configs/collegemsg_sprint01.json'))
    config = config.model_copy(update={'dataset': config.dataset.model_copy(update={
        'path': 'events.txt', 'sha256': hashlib.sha256(raw).hexdigest()}), 'investigation_family': 'auto'})
    built = build_bounded_graph(tmp_path, config.dataset, config.window)
    inp = InvestigationInput(case_id=built.record.graph_id, question='Retrieve activity lookalikes',
                             request={'family': 'auto'}, graph=built.graph, record=built.record, spec=config.experiment)
    original = engine.run_tool
    def fail_analysis(rt, state, ctx, index, call):
        return None if call['tool'] == 'behavior_similarity' else original(rt, state, ctx, index, call)
    monkeypatch.setattr(engine, 'run_tool', fail_analysis)
    plan = {'decision': 'run', 'family': 'behavior', 'tool_calls': [{'tool': 'behavior_similarity'}]}
    result = run_investigation(inp, config, MockProvider(script={'planner': [json.dumps(plan)]}),
                              tmp_path / 'runs', cache_dir=None,
                              input_ref={'kind': 'collegemsg', 'data_root': str(tmp_path)})
    assert result.outcome.status == 'partial'
    assert 'behavior_similarity' in result.result.missing_analyses


def test_oversized_behavior_request_is_explicit_pretool_refusal(tmp_path, monkeypatch):
    from blackgrid.data.collegemsg import build_graph
    import blackgrid.workflow.runner as runner
    monkeypatch.setattr(runner, 'renderer', lambda rt, state: None)
    raw = '\n'.join(f'0 {n} 1' for n in range(1, 1101)).encode()
    (tmp_path / 'events.txt').write_bytes(raw)
    config = load_config(Path('configs/collegemsg_sprint01.json'))
    config = config.model_copy(update={'scope': 'full_dataset', 'dataset': config.dataset.model_copy(update={
        'path': 'events.txt', 'sha256': hashlib.sha256(raw).hexdigest()}), 'investigation_family': 'auto'})
    built = build_graph(tmp_path, config)
    inp = InvestigationInput(case_id=built.record.graph_id, question='Find behavioral clusters',
                             request={'family': 'auto'}, graph=built.graph, record=built.record, spec=config.experiment)
    result = run_investigation(inp, config, MockProvider(), tmp_path / 'runs', cache_dir=None,
                              input_ref={'kind': 'collegemsg', 'data_root': str(tmp_path)})
    assert result.result.verdict == 'rejected' and not result.result.tool_calls
    report = (result.run_dir / 'report.md').read_text(encoding='utf-8')
    assert '1,000 nodes' in report and '1,101 nodes' in report and 'first-window' in report


@pytest.mark.parametrize('question', [
    'For every activity segment, report its population and the share flagged by each of the two outlier rules.',
    'Report outlier counts within each group.',
    'Compare flagged candidates across the activity segments.',
])
def test_grouped_outlier_obligations_need_memberships_and_denominators(question):
    allowed, calls, _ = validate_structural(question, {'family': 'behavior'}, {
        'decision': 'run', 'tool_calls': [{'tool': 'behavior_anomalies'}]})
    assert allowed
    assert [c['tool'] for c in calls] == ['behavior_features', 'behavior_clustering', 'behavior_anomalies']


@pytest.mark.parametrize('question', [
    'Do those behavioral outlier flags prove the participants are scammers?',
    'Confirm whether these anomaly candidates are fraudulent users.',
    'Identify malicious participants from these anomaly scores.',
])
def test_behavioral_scores_cannot_verify_criminal_identity(question):
    from blackgrid.agent.inquiry import unsupported_scope
    assert 'cannot prove fraud' in unsupported_scope(question)
    assert family(question, {'family': 'auto'}) == 'clarify'


def test_descriptive_screening_and_no_outlier_request_remain_available():
    from blackgrid.agent.inquiry import unsupported_scope
    assert unsupported_scope('Show unusual profiles without confirming fraud.') is None
    assert unsupported_scope('Screen outliers without treating them as confirmed wrongdoing.') is None
    allowed, calls, _ = validate_structural('Show both activity segmentation and closest-profile retrieval without an outlier screen.',
        {'family': 'behavior'}, {'decision': 'run', 'tool_calls': [{'tool': 'behavior_clustering'}, {'tool': 'behavior_similarity'}]})
    assert allowed and 'behavior_anomalies' not in {c['tool'] for c in calls}
    allowed, calls, _ = validate_structural('Show activity segmentation and closest-profile retrieval, leaving out anomaly detection.',
        {'family': 'behavior'}, {'decision': 'run', 'tool_calls': [{'tool': 'behavior_clustering'}, {'tool': 'behavior_similarity'}, {'tool': 'behavior_anomalies'}]})
    assert allowed and {c['tool'] for c in calls} == {'behavior_features', 'behavior_clustering', 'behavior_similarity'}
