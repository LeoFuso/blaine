#!/usr/bin/env python3
"""Create the Blaine-owned logical DB/schema on existing native PostgreSQL.

Run as the existing Hub service user. Uses existing sudo-to-postgres for this
bounded migration only; runtime uses Unix peer auth, no password or sudo.
Does not alter HBA, restart PostgreSQL, or touch vendor-managed databases.
"""
import getpass
from pathlib import Path
import re
import subprocess

def main():
    user = getpass.getuser()
    if user == 'root' or not re.fullmatch('[a-z_][a-z0-9_]*', user):
        raise SystemExit('Run as the existing non-root Hub service user')
    def sql(query, database='postgres'):
        p = subprocess.run(['sudo', '-n', '-u', 'postgres', 'psql', '-XAt', '-v', 'ON_ERROR_STOP=1',
                            '-d', database], input=query, text=True, capture_output=True)
        if p.returncode:
            raise SystemExit('STOP: registry migration failed; inspect PostgreSQL locally (details suppressed)')
        return p.stdout.strip()
    role = sql(f"SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication FROM pg_roles WHERE rolname='{user}'")
    if role == 't':
        raise SystemExit('STOP: existing service role is privileged')
    if not role:
        sql(f'CREATE ROLE "{user}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION')
    owner = sql("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='blaine'")
    if owner and owner != 'postgres':
        raise SystemExit('STOP: existing blaine database ownership differs')
    if not owner:
        sql('CREATE DATABASE blaine OWNER postgres')
    unexpected = sql("SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema','blaine_workstations')", 'blaine')
    if unexpected != '0':
        raise SystemExit('STOP: unexpected application tables in blaine database')
    exists = sql("SELECT count(*) FROM pg_namespace WHERE nspname='blaine_workstations'", 'blaine')
    if exists == '0':
        schema = Path(__file__).resolve().parents[2] / 'client/internal/workstation/schema.sql'
        sql('BEGIN;\n'+schema.read_text()+'\nCOMMIT;', 'blaine')
    if sql('SELECT version FROM blaine_workstations.schema_version', 'blaine') != '1':
        raise SystemExit('STOP: registry schema version mismatch')
    sql(f'''REVOKE ALL ON DATABASE blaine FROM PUBLIC;
GRANT CONNECT ON DATABASE blaine TO "{user}";
GRANT USAGE ON SCHEMA blaine_workstations TO "{user}";
GRANT SELECT ON blaine_workstations.schema_version TO "{user}";
GRANT SELECT, INSERT, UPDATE, DELETE ON blaine_workstations.workstation, blaine_workstations.connection TO "{user}";''', 'blaine')
    print('Registry schema v1 ready on existing PostgreSQL; runtime uses local peer authentication')

if __name__ == '__main__':
    main()
