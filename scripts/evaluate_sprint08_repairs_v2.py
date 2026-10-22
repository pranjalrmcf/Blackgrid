"""Real-only fresh repair follow-up; preserves the original 24-case harness and results."""
from __future__ import annotations
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
import evaluate_sprint08 as base

DEPENDENCY_SHA = '9a7f85e6c2372c5300d4f097d8e1aaedc4d52a9453a6b18040ae8abb4e372f39'
assert base.digest(Path(base.__file__)) == DEPENDENCY_SHA, 'Original numerical evaluator changed'
base.OUT = base.ROOT / 'runs/sprint08-repairs-followup-v2'
base.PROTOCOL = base.ROOT / 'protocols/sprint08_repairs_followup_v2.json'
base.__file__ = __file__  # the shared dispatcher invokes this wrapper in each worker process


def audit():
    from blackgrid.contracts import RunConfig
    from blackgrid.data.collegemsg import build_graph
    from blackgrid.evaluation.scoring import verify_artifacts
    from blackgrid.evaluation.sprint4_live import claim_diagnostics
    out = base.OUT
    freeze, execution = base.read(out / 'freeze.json'), base.read(out / 'execution.json')
    assert base.digest(base.PROTOCOL) == freeze['protocol_sha256']
    built = build_graph(base.ROOT, RunConfig.model_validate(base.read(out / 'base_config.json')))
    values, count = base.independent_features(built.table.events, built.record.window_start_ts, built.record.window_end_ts)
    rows = []
    for case in base.read(base.PROTOCOL)['cases']:
        marker = out / (case['id'] + '.json')
        row = base.read(marker) if marker.exists() else {'id': case['id'], 'error': 'not dispatched'}
        checks = {'source_unchanged': execution['source_unchanged']}
        try:
            run = Path(row['run_dir'])
            docs = verify_artifacts(run)
            inv = docs['investigation.json']
            checks.update(verified_artifacts=True, real_mode=inv['cost']['mode'] == 'live')
            checks['claim_numbers_bound'] = all(claim_diagnostics(c, docs)['numbers_bound'] for c in inv['reported_claims'])
            checks['prompt_privacy'] = all(not base.private_fields(json.loads(m['content']))
                for line in (run / 'llm_trace.jsonl').read_text(encoding='utf-8').splitlines()
                for m in json.loads(line).get('messages', []) if m.get('role') == 'user')
            if case['expected'] == 'answer':
                checks['completed_correct_family'] = inv['status'] == 'completed' and inv['family'] == 'behavior'
                executed = [t['tool'] for t in inv['tool_calls'] if t['outcome'] == 'completed']
                checks['exact_requested_tools'] = sorted(executed) == sorted(case['required_tools'])
                checks['accepted_claims'] = bool(inv['reported_claims']) and all(c['accepted'] for c in inv['critic_decisions'])
                checks.update(base.numeric_checks(docs, values, count, case['required_tools']))
                if case['id'].startswith('J'):
                    a, c = docs['behavior_anomalies.json'], docs['behavior_clustering.json']
                    groups = a['summary']['cluster_comparison']
                    labels = {r['node']: r['cluster'] for r in c['rows']}
                    sizes = Counter(labels.values())
                    candidates = Counter(labels[r['node']] for r in a['rows'] if r['candidate'])
                    baseline = Counter(labels[r['node']] for r in a['rows'] if r['count_baseline_candidate'])
                    checks['joined_counts_and_shares'] = all(g['size'] == sizes[g['cluster']] and
                        g['candidates'] == candidates[g['cluster']] and
                        g['count_baseline_candidates'] == baseline[g['cluster']] and
                        base.close(g['candidate_fraction'], candidates[g['cluster']] / sizes[g['cluster']]) and
                        base.close(g['count_baseline_fraction'], baseline[g['cluster']] / sizes[g['cluster']]) for g in groups.values())
                    checks['joined_local_membership'] = all(r['cluster'] == labels[r['node']] for r in a['rows'])
                    checks['joined_claims_in_answer'] = all('Behavioral cluster ' + str(g['cluster']) + ' contains' in
                        (run / 'report.md').read_text(encoding='utf-8') for g in groups.values())
            else:
                checks['pretool_refusal'] = inv['verdict'] == 'rejected' and not inv['tool_calls'] and not inv['reported_claims']
                if case['expected'] == 'size_refusal':
                    text = (run / 'report.md').read_text(encoding='utf-8')
                    checks['size_explanation_in_report'] = ('1,000 nodes' in text and '1,899 nodes' in text and 'first-window' in text)
            row.update(checks=checks, automated_pass=all(checks.values()))
        except Exception as exc:
            row.update(checks=checks, automated_pass=False, audit_error=type(exc).__name__ + ': ' + str(exc)[:400])
        rows.append(row)
    conn = sqlite3.connect(base.ROOT / 'runs/workflow.sqlite')
    conn.row_factory = sqlite3.Row
    ops = [dict(r) for r in conn.execute("SELECT operations.*, runs.run_dir FROM operations JOIN runs USING(run_id) WHERE kind='llm' AND run_id LIKE 'sprint08-repairs-followup-v2-%'")]
    conn.close()
    cost, unresolved, reserved = 0., 0, 0.
    for op in ops:
        receipt = Path(op['run_dir']) / op['receipt_path'] if op['receipt_path'] else None
        if receipt and receipt.is_file() and base.digest(receipt) == op['receipt_sha256']:
            cost += op['actual_usd']
        elif op['state'] == 'dispatched' or op['category'] == 'uncertain':
            unresolved += 1
            reserved += max(op['reserved_usd'], op['actual_usd'])
    project, sprint = base.spending()
    result = dict(rows=rows, execution=execution, accounting=dict(actual_usd=cost, unresolved_calls=unresolved,
        unresolved_reserved_usd=reserved, llm_calls=len(ops), project_accounted_usd=project,
        remaining_usd=3-project, within_budget=max(project, sprint)<=3),
        dependency_sha256=DEPENDENCY_SHA, ui_review='pending actual browser verification')
    base.save(out / 'audit.json', result)
    print(json.dumps(dict(automated_pass=sum(r['automated_pass'] for r in rows), total=len(rows),
        failures={r['id']: {'checks':[k for k,v in r.get('checks',{}).items() if not v], 'error':r.get('audit_error')} for r in rows if not r['automated_pass']},
        accounting=result['accounting'], execution=execution), indent=2))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'worker':
        base.worker(sys.argv[2])
    elif len(sys.argv) > 1 and sys.argv[1] == 'audit':
        audit()
    else:
        base.run()
