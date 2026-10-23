"""Idle-only local deployment with private offline backup and cumulative checks."""
import json
import secrets
import time
from datetime import UTC,datetime
from pathlib import Path
import verify_phase6 as verification
from verify_phase6 import ROOT,docker


def main(*, phase='7'):
    assert phase in ('7','8')
    output = ROOT/f'docs/production_phase{phase}/evidence'
    output.mkdir(parents=True,exist_ok=True)
    # Read-only preflight; leave the current service untouched if work is active.
    code = """import sqlite3,json
c=sqlite3.connect('file:/app/runs/api/jobs.sqlite?mode=ro',uri=True)
print(c.execute("select count(*) from jobs where state in ('queued','running')").fetchone()[0])
"""
    assert int(docker('exec','-i','blackgrid-blackgrid-1','python','-',code=code)) == 0,'Wait for active jobs before deployment'
    stamp = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(3)
    name = 'jobs-pre-phase'+phase+'-'+stamp+'.sqlite'
    code = """import sqlite3,json,hashlib
from contextlib import closing
with closing(sqlite3.connect('/app/runs/api/jobs.sqlite')) as src, closing(sqlite3.connect('/app/runs/api/"""+name+"""')) as dst:
    src.backup(dst)
    src.row_factory=sqlite3.Row
    rows=[dict(r) for r in src.execute('select * from jobs order by id')]
    print(json.dumps({'backup':'"""+name+"""','original_jobs':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),'api_charged_usd':src.execute('select sum(charged_usd) from jobs').fetchone()[0]}))
"""
    baseline = json.loads(docker('exec','-i','blackgrid-blackgrid-1','python','-',code=code))
    (output/'pre_deploy.json').write_text(json.dumps(baseline,indent=2),encoding='utf-8')
    private = ROOT/f'.secrets/phase{phase}-backups'
    private.mkdir(mode=0o700,exist_ok=True)
    docker('compose','stop','blackgrid')
    try:
        info = json.loads(docker('run','--rm','--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--memory','2g','--cpus','1','--pids-limit','128',
            '--tmpfs','/tmp:size=64m,mode=1777','--mount','type=volume,source=blackgrid_blackgrid-state,target=/app/runs',
            '--mount',f'type=bind,source={private},target=/private',
            '--entrypoint','python','blackgrid:phase'+phase,'-m','blackgrid.operations.backup',
            'create','/app/runs','/private/'+stamp))
        info['private_destination'] = f'.secrets/phase{phase}-backups/'+stamp
        (output/'production_backup.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    except Exception:
        # The old container still has its original image/config/volume.
        docker('start','blackgrid-blackgrid-1')
        raise
    assert 'image: blackgrid:phase'+phase in (ROOT/'docker-compose.yml').read_text()
    verification.OUTPUT = output
    verification.main(initial_stopped=True,repeat_warm=phase=='8')


if __name__ == '__main__': main()
