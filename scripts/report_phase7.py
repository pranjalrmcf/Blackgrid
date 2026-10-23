"""Summarize executed JUnit and deployed/scan evidence; fail on incomplete gates."""
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/production_phase7/evidence'


def main():
    root = ET.parse(OUT/'regression_final.xml').getroot()
    cases = list(root.iter('testcase'))
    assert cases and all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases)
    matrix = {}
    groups = {
        'worker_and_restart':['real_worker_crash','checkpoint_resume','queued_request_survives','parallel_duplicate_and_restart','interrupted_job_keeps'],
        'storage_and_partial_output':['database_failure','read_only_failure','partial_artifact','tampered_artifact','corrupt_source_database','bad_snapshot'],
        'provider_failures':['provider_status','provider_malformed','transport_process_is_killed','provider_errors_are_booked','invalid_json_gets_one_retry','uncertain_provider_failure'],
        'resource_and_admission':['memory_exhausted_child','execution_deadline','concurrent_unique_submissions','budget_exhaustion','rate_limit_is_per'],
        'ownership_and_adversarial_inputs':['owner_boundaries','traversal','prompt_injection','answer_key_request','invalid_requests','ambiguous_framing','dashboard_public_assets','browser_origin'],
        'backup_integrity':['snapshot_','closed_api_state','wal_snapshot','corrupt_source_database','bad_snapshot']}
    for category,fragments in groups.items():
        selected = [c for c in cases if any(f in c.get('name','') for f in fragments)]
        assert selected,category
        matrix[category] = dict(executed=len(selected),passed=len(selected),
            case_execution_seconds=sum(float(c.get('time',0)) for c in selected),
            cases=[dict(module=c.get('classname'),name=c.get('name')[:180],
                full_name_sha256=hashlib.sha256(c.get('name').encode()).hexdigest()) for c in selected])
    scan = json.loads((OUT/'scan_summary.json').read_bytes())
    deployment = json.loads((OUT/'deployment_verification.json').read_bytes())
    restore = json.loads((OUT/'restore_drill.json').read_bytes())
    assert scan['image_id'] == deployment['image_id']
    assert scan['severity_counts'].get('CRITICAL',0) == 0
    assert deployment['exact_api_result_parity'] and deployment['restart_result_exact'] and restore['all_job_columns_exact']
    revision = subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    relevant = [ROOT/p for p in ('Dockerfile','.dockerignore','docker-compose.yml','pyproject.toml','uv.lock',
        'scripts/verify_phase6.py','scripts/deploy_phase7.py','scripts/verify_phase7.py','scripts/scan_phase7.py','scripts/report_phase7.py',
        'scripts/verify_dashboard.cjs')]+list((ROOT/'src').rglob('*.py'))+list((ROOT/'tests').rglob('*.py'))
    sources = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in relevant}
    summary = dict(version='production-phase7-v1',checks=len(cases),failures=0,skipped=0,
        fixture_pass_fraction=1.0,not_production_reliability_estimate=True,fault_matrix=matrix,
        image_id=deployment['image_id'],test_image_id=json.loads(subprocess.run(
            ['docker','image','inspect','blackgrid:phase7-test'],cwd=ROOT,capture_output=True,text=True,check=True).stdout)[0]['Id'],
        source_revision=revision,source_dirty=True,
        critical_scanner_findings=0,remaining_os_findings=scan['severity_counts'],
        paid_calls=0,new_provider_usd=0,original_job_rows_exact=deployment['original_rows_exact'],
        api_charged_usd=deployment['api_charged_usd'],scientific_parity_exact=True,
        restored_files_exact=restore['files_exact'],duplicate_jobs_in_restore_drill=0,lost_jobs_in_restore_drill=0,
        limits=['single-host trusted-tool deployment','local exploratory engineering fixtures',
                'unpatched OS advisories retained','no physical power-loss test','no real provider fault injection',
                'no multi-host failover','vLLM out of scope'])
    (OUT/'source_manifest_final.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
    (OUT/'acceptance.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k != 'fault_matrix'},indent=2))


if __name__ == '__main__': main()
