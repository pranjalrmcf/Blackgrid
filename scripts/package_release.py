"""Record immutable source/image/scan identities; no registry upload or secret reads."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/production_phase9/evidence'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ci', action='store_true')
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    def command(argv):
        return subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=True).stdout
    image = json.loads(command(['docker', 'image', 'inspect', 'blackgrid:phase9']))[0]
    scanfile = output / 'scan_phase9.json'
    if args.ci:
        # CI scanned this local immutable image directly, never a mutable registry tag.
        (output/'scan_summary.json').write_text(json.dumps(dict(
            image_id=image['Id'], scan_sha256=hashlib.sha256(scanfile.read_bytes()).hexdigest(),
            scanner_digest='aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222',
            scanner=json.loads((output/'scanner_version.json').read_bytes()),
        ), indent=2), encoding='utf-8')
    files = list((ROOT/'src').rglob('*'))
    files += [ROOT/p for p in ('pyproject.toml', 'uv.lock', 'Dockerfile', '.dockerignore',
                               'protocols/production_phase9_v1.json', 'docker-compose.yml',
                               'docker-compose.benchmark.yml')]
    controls = list((ROOT/'tests').rglob('*.py'))+list((ROOT/'.github').rglob('*.yml'))
    controls += [ROOT/'scripts'/p for p in ('release_gate.py','package_release.py',
        'promote_phase9.py','verify_phase9.py','deploy_phase9.py','deploy_phase7.py',
        'verify_phase6.py','run_phase6.py','scan_phase7.py')]
    hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(files) if p.is_file() and '__pycache__' not in p.parts}
    manifest = dict(version='1.0.0', scope='local-restricted', image_id=image['Id'],
        source_revision=command(['git','rev-parse','HEAD']).strip(),
        source_dirty=bool(command(['git','status','--porcelain','--untracked-files=no']).strip()),
        source_hashes=hashes, lock_sha256=hashes['uv.lock'],
        verification_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(controls)},
        scan_sha256=hashlib.sha256(scanfile.read_bytes()).hexdigest(),
        schema_change='none in phase9; additive legacy initialization is unchanged',
        provider_calls_during_release=0, public_release_approved=False)
    (output/'release_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='source_hashes'}, indent=2))


if __name__ == '__main__': main()
