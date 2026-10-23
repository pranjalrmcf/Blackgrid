"""Join final local evidence without rewriting historical results or private ledgers."""
import hashlib
import json
import time
from pathlib import Path

from release_gate import evidence, junit, require

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/production_phase9'


def load(name): return json.loads((OUT/name).read_bytes())


def main():
    manifest = load('evidence/release_manifest.json')
    deployed = load('evidence/deployment_verification.json')
    rollback = load('evidence/rollback.json')
    browser = load('evidence/browser_verification.json')
    scan = load('evidence/scan_summary.json')
    require(deployed['image_id'] == rollback['image_id'] == manifest['image_id'] == scan['image_id'],
            'Release/deployment/rollback/scan image mismatch')
    for name,digest in (manifest['source_hashes'] | manifest['verification_hashes']).items():
        require(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, 'Release source identity changed')
    gates = evidence(OUT, deployed['image_id'], 'local-restricted', now=time.time())
    ci = junit(OUT/'ci/regression.xml')
    require(ci['collected'] == gates['tests']['collected'] and ci['skipped'] == 2,
            'Private-free CI collection differs from complete local regression')
    require(browser['login'] and browser['live_updates'] and browser['logout_revoked']
        and browser['page_errors'] == browser['external_page_requests'] == 0,
        'Browser verification incomplete')
    require(deployed['source_and_assets_exact'] and deployed['exact_api_result_parity']
        and deployed['restart_result_exact'] and deployed['cache_survives_restart']
        and deployed['warm_cache_hits'] == 3 and rollback['all_job_columns_and_spend_exact'],
        'Deployment/recovery compatibility incomplete')
    attempts = list((OUT/'benchmark').glob('*/reconciliation.json'))
    require(len(attempts) == 1, 'Final benchmark evidence is ambiguous')
    workload = json.loads(attempts[0].read_bytes())
    require(workload['reconciled'] and workload['image_id'] == deployed['image_id'], 'Load image mismatch')
    require(all(s['incomplete'] == s['censored'] == s['unexpected_errors'] == 0 for s in workload['stages']),
            'Final workload has failed outcomes')
    quality = (OUT/'quality_final.log').read_text()
    require('All checks passed!' in quality and 'Success: no issues found' in quality, 'Quality checks missing')
    report = dict(version='1.0.0', phase9='complete_for_local_restricted_scope',
        image_id=deployed['image_id'], full_regression=gates['tests'], private_free_ci_regression=ci,
        quality='fatal lint, three-file formatting and strict release-gate typing passed',
        local_ci_equivalent='passed', remote_github_actions='not_verified_by_this_local_report',
        staging='passed', synthetic_restore='passed', production_rollback_and_return='passed',
        dashboard='passed', source_and_assets_exact=deployed['source_files'],
        original_job_rows_exact=deployed['original_rows_exact'],
        rollback_job_rows_exact=rollback['state_before_rollback']['jobs'],
        cumulative_retained_api_spend_usd=deployed['api_charged_usd'],
        new_provider_usd=0, real_provider_calls=0,
        benchmark_attempt=workload['attempt'], accepted_jobs=workload['ledger_jobs'],
        completed_jobs=sum(s['completed'] for s in workload['stages']),
        explicit_queue_rejections=sum(s['rejected'] for s in workload['stages']),
        scan_severity_counts=scan['severity_counts'], public_release_approved=False,
        production_slo_compliance='not established', multi_host='not implemented',
        vllm='out of scope', limitations=['unfixed OS advisories',
        'short closed-loop synthetic/mock workload, not sustained real-provider capacity',
        'one worker and eight queue slots', 'restore is not a power-loss disaster simulation',
        'GitHub environment and branch protection require repository-owner configuration'])
    (OUT/'evidence/final_acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__': main()
