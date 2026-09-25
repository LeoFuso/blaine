"""Read-only prerequisites for the additive CP.2 native suite; never provision."""
from pathlib import Path
import subprocess
import urllib.request
from verification.suite import ProbeResult, ProbeStatus, register_probe


@register_probe('mirix-cp2')
def probe_mirix(_suite_dir, env):
    python = Path.home() / 'workspace/mirix/.venv/bin/python'
    if not python.is_file():
        return ProbeResult(ProbeStatus.UNAVAILABLE, 'Existing MIRIX interpreter unavailable')
    # Execute only this trusted fixed probe in a separate process. No candidate
    # worktree modules enter the scheduler, and no credentials/content are emitted.
    code = '''
import configparser, stat, os
from pathlib import Path
from urllib.parse import urlsplit
import psycopg2
p=Path.home()/'.mirix/config'
for item in (p,p.parent):
 s=item.stat()
 assert s.st_uid==os.getuid() and not stat.S_IMODE(s.st_mode)&0o077
c=configparser.ConfigParser(interpolation=None);c.read(p)
u=c['recall_storage']['uri'];a=urlsplit(u)
assert u==c['archival_storage']['uri'] and a.hostname=='127.0.0.1' and a.path=='/mirix'
assert not a.query and not a.fragment and a.scheme in ('postgresql','postgresql+pg8000','postgresql+psycopg2')
db=psycopg2.connect(a._replace(scheme='postgresql').geturl(),connect_timeout=5)
db.set_session(readonly=True)
with db,db.cursor() as cur:
 cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name='raw_memory'")
 assert cur.fetchone()
 cur.execute("SELECT 1 FROM clients c JOIN users u ON u.organization_id=c.organization_id WHERE NOT c.is_deleted AND NOT u.is_deleted LIMIT 1")
 assert cur.fetchone()
db.close()
'''
    try:
        result = subprocess.run([str(python), '-c', code], capture_output=True, timeout=15)
        if result.returncode:
            return ProbeResult(ProbeStatus.UNAVAILABLE, 'MIRIX database/credential/schema prerequisite unavailable')
        service = subprocess.run(['systemctl', '--user', 'is-active', 'blaine-mirix.service'],
                                 capture_output=True, timeout=10)
        if service.returncode or service.stdout.strip() != b'active':
            return ProbeResult(ProbeStatus.UNAVAILABLE, 'Accepted MIRIX user service unavailable')
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        for port in (8531, 8001):
            with opener.open(f'http://127.0.0.1:{port}/health', timeout=5) as response:
                if response.status != 200:
                    raise ValueError()
        return ProbeResult(ProbeStatus.AVAILABLE, 'Existing MIRIX/PostgreSQL and local embedding service available')
    except Exception:
        return ProbeResult(ProbeStatus.UNAVAILABLE, 'Existing MIRIX/local embedding prerequisite unavailable')
