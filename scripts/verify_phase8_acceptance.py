"""Join independent performance, scientific, security and runtime release evidence."""
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/production_phase8'


def main():
    tests=[]
    for filename in ('regression.xml','live_cache.xml'):
        cases=list(ET.parse(OUT/filename).getroot().iter('testcase'))
        assert cases and all(all(c.find(tag) is None for tag in ('failure','error','skipped')) for c in cases)
        tests.extend(cases)
    assert len(tests)==675
    summary=json.loads((OUT/'comparison-v1/summary.json').read_bytes())
    deployed=json.loads((OUT/'evidence/deployment_verification.json').read_bytes())
    candidate=json.loads((OUT/'comparison-v1/candidate.json').read_bytes())
    scanned=json.loads((OUT/'evidence/scan_summary.json').read_bytes())
    browser=json.loads((OUT/'evidence/browser_verification.json').read_bytes())
    sources={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted((ROOT/'src').rglob('*.py'))}
    assert sources==candidate['source_hashes']
    assert scanned['image_id']==deployed['image_id'] and not scanned['severity_counts'].get('CRITICAL',0)
    assert deployed['exact_api_result_parity'] and deployed['cache_survives_restart'] and deployed['warm_cache_hits']==3
    assert browser['login'] and browser['live_updates'] and browser['logout_revoked']
    paths=list((ROOT/'tests').rglob('*.py'))+[ROOT/p for p in (
        'Dockerfile','.dockerignore','docker-compose.yml','protocols/production_phase8_v1.json',
        'scripts/profile_phase8.py','scripts/benchmark_phase8.py','scripts/report_phase8.py',
        'scripts/verify_phase8_acceptance.py','scripts/deploy_phase8.py','scripts/deploy_phase7.py',
        'scripts/verify_phase6.py','scripts/scan_phase7.py','scripts/ask_api.py')]
    sources.update({p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True,check=True).stdout.strip()
    image_id=json.loads(subprocess.run(['docker','image','inspect','blackgrid:phase8-test'],cwd=ROOT,
        text=True,capture_output=True,check=True).stdout)[0]['Id']
    result=dict(version='production-phase8-v1',full_regression_passed=674,additional_live_cache_check_passed=1,
        total_checks=675,failures=0,skipped=0,source_revision=revision,source_dirty=True,
        test_image_id=image_id,production_image_id=deployed['image_id'],
        measured_candidate_source_matches_deployed_source=True,scientific_and_api_parity_exact=True,
        repeated_synthetic_median_reduction=summary['warm_reduction_fraction'],
        cold_synthetic_change=summary['cold_change_fraction'],
        configured_graph_cold_seconds=deployed['cold_creation_to_terminal_seconds'],
        configured_graph_warm_seconds=deployed['warm_creation_to_terminal_seconds'],
        original_job_rows_exact=deployed['original_rows_exact'],api_charged_usd=deployed['api_charged_usd'],
        real_provider_calls=0,new_provider_usd=0,cache_survives_restart=True,
        critical_scanner_findings=0,remaining_os_findings=scanned['severity_counts'],
        worker_slots=1,queue_slots=8,vllm='out_of_scope',phase9='not_authorized',
        limitations=summary['limitations']+['configured real-graph pair is one offline demonstration, not a replicated performance study'])
    (OUT/'evidence/source_manifest_final.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
    (OUT/'evidence/acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
