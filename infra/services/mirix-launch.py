#!/usr/bin/env python3
"""Preserve the existing MIRIX PostgreSQL identity without copying its secret."""
import configparser
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit


def configure():
    source = Path.home() / '.mirix/config'
    for p in [source.parent, source]:
        s=p.stat()
        if s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) & 0o077:
            raise RuntimeError('MIRIX secret configuration must be private to the operator')
    c=configparser.ConfigParser();c.read(source)
    uri=c['recall_storage']['uri']
    if uri != c['archival_storage']['uri']:
        raise RuntimeError('Ambiguous MIRIX database identity')
    target=urlsplit(uri)
    if target.hostname != '127.0.0.1' or target.path != '/mirix':
        raise RuntimeError('Unexpected MIRIX database identity')
    os.environ.update(MIRIX_PG_URI=uri,MIRIX_DEBUG='false',MIRIX_LOG_LEVEL='INFO',
                      MIRIX_PG_ECHO='false',MIRIX_LANGFUSE_ENABLED='false')


if __name__=='__main__':
    configure()
    root=Path.home()/'workspace/mirix'
    os.chdir(root)
    os.execv(str(root/'.venv/bin/python'),[str(root/'.venv/bin/python'),
        'scripts/start_server.py','--host','127.0.0.1','--port','8531','--log-level','info'])
