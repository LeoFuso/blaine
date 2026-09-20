# Paused physical acceptance evidence

LIVE BACKUP ACCEPTANCE = PAUSED

These files retain the attempted implementation and observed diagnostics for a
later bounded pass. They are not an accepted fix or an operational entrypoint.
Do not execute the archived runner or apply the patch during the pause.

- `accept-physical.py.txt`: exact last attempted runner, archived as text. Its
  eventual timer-enablement path was never reached. Ansible does not deploy it.
- `unaccepted-identity-attempt.patch`: the attempted setpriv/public-cwd switch
  and diagnostic categorization, relative to the maintained backup script.
  These changes were removed from maintained code; both identity probes failed.
- `pg-probes.json`: retained controlled SELECT 1 probe results from the host;
  no new probes were run to create this checkpoint.

The maintained implementation keeps the previous runuser path, whose live
systemd execution is failing. This is not a fix. The installed host copy still
contains the attempted variant; no host files were reconciled during the pause.
The timer was confirmed disabled/inactive. Review installed/source drift before
any future resumption; do not restart the service merely to reconcile it now.

Volume preparation passed and the missing-mount negative test passed. There is
no accepted physical generation or live restore. See the current D1 runbook and
`infra/physical-first-attempt-d1.json`. Earlier `infra/validation-d1-physical.json`
is historical pre-acceptance evidence; its pending status and hashes describe
that earlier revision, not this checkpoint.
