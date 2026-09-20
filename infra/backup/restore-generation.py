#!/usr/bin/env python3
"""Restore a trusted D1 generation into a disposable Unix-socket-only cluster.

Never connects to a live target. Requires native PostgreSQL 18 extensions used
by the source. The physical acceptance caller rejects non-default tablespaces.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import subprocess
import tempfile
import uuid

import backup

PG = Path("/usr/lib/postgresql/18/bin")


def restore(snapshot, proof_database=None):
    snapshot = backup.plain_directory(snapshot)
    manifest = backup.verify(snapshot, str(PG))
    if any(not backup.IDENTIFIER.fullmatch(name) for name in manifest["databases"]):
        raise backup.Refused("invalid database names in manifest")
    # pg_dumpall tablespace statements can refer to live filesystem paths.
    globals_sql = (snapshot / "postgres/globals.sql").read_text()
    if "CREATE TABLESPACE" in globals_sql:
        raise backup.Refused("tablespace relocation requires a separately reviewed restore")
    prefix = []
    if os.geteuid() == 0:
        account = pwd.getpwnam("postgres")
        prefix = ["/usr/sbin/runuser", "-u", "postgres", "--"]
    else:
        account = pwd.getpwuid(os.geteuid())
    bootstrap = "d1restore_" + uuid.uuid4().hex[:12]
    with tempfile.TemporaryDirectory(prefix="blaine-d1-restore-") as temporary:
        root = Path(temporary)
        os.chown(root, account.pw_uid, account.pw_gid)
        socket = root / "socket"
        socket.mkdir(mode=0o700)
        os.chown(socket, account.pw_uid, account.pw_gid)
        data = root / "data"
        def command(tool, *args, **kwargs):
            return backup.run(prefix + [str(PG / tool), *args], cwd="/tmp", **kwargs)
        def sql(database, query):
            return command("psql", "-X", "-h", str(socket), "-p", "15432", "-U", bootstrap,
                           "-d", database, "--set", "ON_ERROR_STOP=1", "-Atc", query,
                           stdout=subprocess.PIPE).stdout.decode().strip()
        command("initdb", "-D", str(data), "--username", bootstrap,
                "--auth-local=trust", "--auth-host=reject", "--no-locale", stdout=subprocess.DEVNULL)
        started = False
        try:
            command("pg_ctl", "-D", str(data), "-l", str(root / "postgres.log"),
                    "-o", f"-h '' -k {socket} -p 15432", "-w", "start", stdout=subprocess.DEVNULL)
            started = True
            with (snapshot / "postgres/globals.sql").open("rb") as stream:
                command("psql", "-X", "-h", str(socket), "-p", "15432", "-U", bootstrap,
                        "-d", "template1", "--set", "ON_ERROR_STOP=1", "-f", "-",
                        stdin=stream, stdout=subprocess.DEVNULL)
            if "postgres" in manifest["databases"]:
                sql("template1", "DROP DATABASE postgres")
            restored = []
            for name in manifest["databases"]:
                with (snapshot / "postgres" / (name + ".dump")).open("rb") as stream:
                    command("pg_restore", "-h", str(socket), "-p", "15432", "-U", bootstrap,
                            "-d", "template1", "--create", "--exit-on-error", stdin=stream,
                            stdout=subprocess.DEVNULL)
                tables = int(sql(name, "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema')"))
                restored.append({"database": name, "user_tables": tables})
            proof = None
            if proof_database:
                if proof_database not in manifest["databases"]:
                    raise backup.Refused("proof database is absent from the snapshot")
                proof = sql(proof_database, "SELECT value FROM d1_proof WHERE id=1")
                if proof != "ACME physical SSD proof":
                    raise backup.Refused("restored synthetic row differs")
            artifact_count = 0
            artifact_root = snapshot / "artifacts"
            if artifact_root.exists():
                for artifact in backup.safe_files(artifact_root):
                    if not backup.DIGEST.fullmatch(artifact.name) or backup.sha256(artifact) != artifact.name:
                        raise backup.Refused("restored artifact key/content mismatch")
                    # Restore into a separate temporary location and compare bytes.
                    destination = root / "restored-artifacts" / artifact.relative_to(artifact_root)
                    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    destination.write_bytes(artifact.read_bytes())
                    if backup.sha256(destination) != artifact.name:
                        raise backup.Refused("restored artifact differs")
                    artifact_count += 1
            return {"result": "PASS", "databases": restored, "artifact_count": artifact_count,
                    "synthetic_row_verified": proof is not None, "isolated_cluster": True,
                    "tcp_listeners": False, "complete_durable_brain": False}
        finally:
            if started:
                command("pg_ctl", "-D", str(data), "-m", "fast", "-w", "stop", stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot")
    parser.add_argument("--proof-database")
    args = parser.parse_args()
    try:
        print(json.dumps(restore(Path(args.snapshot), args.proof_database), indent=2))
    except Exception as error:
        raise SystemExit("STOP: " + (str(error) if isinstance(error, backup.Refused) else type(error).__name__))
