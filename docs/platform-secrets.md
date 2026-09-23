# Secret delivery and materialization

Canonical runbook for how Blaine credentials reach a running process. The
architectural decision is [ADR 0023](decisions/0023-runtime-secret-delivery-and-materialization.md);
the implementation is [`infra/secrets.py`](../infra/secrets.py) with declarations
in [`infra/secret-consumers.json`](../infra/secret-consumers.json).

## Architecture

```text
Bitwarden Secrets Manager        source of truth, never a runtime dependency
        |
        | explicit materialization or rotation only
        v
SecretSpec `runtime_secrets` alias    provider resolution; swap the backend here
        |
GNOME Keyring -> materializer    bootstrap authority, never handed to a consumer
        |
        v
~/.config/blaine/secrets/<consumer>.env      0600, operator-owned
        |
        v
systemd service or bounded process
        |
        v
runtime
```

SecretSpec 0.20.0, pinned by SHA-256, owns provider resolution. Blaine owns the
consumer allowlist, destination, atomic activation, verification, bootstrap
withholding and rotation reporting. Changing the remote backend is an alias
change, not a code change.

Machine boot, linger startup, service restart, provider invocation and Task
execution never contact Bitwarden or the keyring. A consumer reads only its own
local credential file.

## Source of truth and bootstrap

Managed secrets live in the Bitwarden Secrets Manager project `blaine-dev`. The
machine-account bootstrap credential stays in GNOME Keyring under the existing
operator convention (`service=leofuso-lab`, `credential=bws-access-token`) and is
read only while materializing. It is withheld from every consumer environment,
including when an operator shell exports `BWS_ACCESS_TOKEN`.

## Consumer declarations

`infra/secret-consumers.json` is committed and contains names, destinations,
permissions and constraints — never values. Each consumer declares the exact keys
it may receive:

| Consumer | Declared secret | Destination | Runtime shape |
| --- | --- | --- | --- |
| `jev` | `TYPESAFE_API_KEY` | `~/.config/blaine/secrets/jev.env` | Bounded worker process; no service |
| `grafana-metrics` | `GRAFANA_CLOUD_METRICS_API_KEY` | `~/.config/blaine/secrets/grafana-metrics.env` | Compatibility check against the existing root-owned Alloy path |

Each consumer also owns a SecretSpec manifest under `infra/secretspec/`, holding
the same key names and nothing else. Separate manifests are deliberate: SecretSpec
profiles **extend** the default profile instead of isolating from it, so a shared
manifest would let one consumer resolve another's secrets. Blaine additionally
filters the resolver's output to the declared allowlist and refuses a manifest
that disagrees with the declaration.

### When the keyring prompts

The login keyring is unlocked by `gkr-pam` at graphical login and stays unlocked
for the session, so materialization normally runs without any prompt. A prompt
appears only if materialization runs with no unlocked keyring — before any
graphical login in that boot, over SSH without a session keyring, or after the
keyring was explicitly locked. That is the single deliberate interactive boundary,
it is bounded to the explicit materialization action, and it never applies to
runtime: a consumer starts from its local credential with the keyring, Bitwarden
and SecretSpec all unavailable.

## Operations

```sh
python3 infra/secrets.py status                 # local state only; no remote access
python3 infra/secrets.py materialize jev        # explicit; reaches Bitwarden
python3 infra/secrets.py verify jev             # presence, permissions, declared keys
python3 infra/secrets.py run jev -- <command>   # exec with only this consumer's secrets
python3 infra/accept-secrets.py                 # boot-independence and least-secret acceptance
```

`status` and `verify` never contact the secret manager and never print a value.
`materialize` is the only command that reaches Bitwarden, and it is a bounded
operator capability rather than a general credential-store permission.

### Adding a secret

Declare the consumer and key in `secret-consumers.json`, store the value in the
`blaine-dev` project under the same key, run `materialize`, then `verify`. If a
service consumes it, point that unit at the consumer's credential file and
restart only that unit.

### Removing a secret

Delete the declaration, remove the local credential file, and remove the value
from Bitwarden. A consumer that still expects the key will fail its own
verification rather than start with a partial credential.

### Rotation

```text
update the value in Bitwarden
    -> python3 infra/secrets.py materialize <consumer>
    -> python3 infra/secrets.py verify <consumer>
    -> restart only the affected service, if any
    -> confirm readiness
```

**Rotation is not a reload, and consumers behave in two distinct ways.**

A rotated remote value does not reach a consumer until materialization runs. That
staleness is deliberate and visible: it is the price of removing the secret
manager from the runtime path.

Once materialization has run, the local file holds the new value, but a process
that already started still holds the **old** value, because an environment is
copied at exec and never refreshed. `materialize` reports this explicitly, giving
`rotation.value_changed`, the declared `service` and `restart_required`, and it
restarts nothing itself.

| Consumer shape | Behaviour during rotation |
| --- | --- |
| Bounded process started per invocation, such as `jev` today | Picks up the new value on its next invocation; nothing to restart and no window |
| Long-lived service | Keeps serving with the previous value until it is restarted; `restart_required` is reported so the operator restarts only that unit |

The dangerous case is a backend that **revokes** the old credential at rotation:
the local file and the remote agree, while a still-running service holds a value
that no longer authenticates. Rotate such a credential by materializing and then
restarting the declared service promptly, and prefer backends that allow an
overlap window. Blaine does not detect this for you today — no consumer currently
declares a service, and nothing reloads a credential in place.

Rotation never requires a reboot and never restarts unrelated services.

### Recovery

A lost local credential is re-materialized. A lost bootstrap credential is
restored into the keyring before materializing. Neither affects an already
running consumer, because runtime never reads either source.

## Security properties

Materialization validates that each declared secret exists, is non-empty, meets
its declared minimum length, contains no shell-hostile characters and is not a
placeholder. The credential is written through a private temporary file that is
`0600` from creation, fsynced and atomically renamed, so a failure leaves a
previously valid credential untouched. Reports and failures carry state and
categories, never values: a rejected value is never echoed into a diagnostic.

Consumers receive only their declared keys, with other consumers' secrets and
secret-manager authority stripped before exec. Values never enter Git, evidence,
prompts, logs or process arguments.

## Changing the remote backend

The backend lives behind one alias:

```sh
~/.local/share/blaine/runtime/bin/secretspec config global provider add \
    runtime_secrets "bws://<project-uuid>"
```

Substitution was proven live: swapping Bitwarden for another backend changed the
resolved value while the Jev provider source, the consumer declaration, the
wrapper and the manifest stayed byte-identical, with a one-line delta.

| Target | Alias | Bootstrap | Manifest |
| --- | --- | --- | --- |
| Vault / OpenBao | `vault://<host>:<port>/<mount>/<path>` | `VAULT_TOKEN` or `BAO_TOKEN` | unchanged (inferred; not live-tested) |
| AWS Secrets Manager | `awssm://<region>` | AWS credential chain | **per-secret `ref = { item = … }`** unless the AWS name matches the key |

No Blaine source change is needed for any of them. The `ref` AWS requires is
backend-coupling: a manifest carrying one stops resolving against other backends.

## Deliberately not supported

No secret-management server, broker, Vault or OpenBao deployment, and no
long-lived secret daemon. No custom cryptography. No automatic rotation, no
automatic service restart, and no runtime fetch or refresh. No dynamic or
short-lived credentials. Multi-host distribution is out of scope; each host
materializes locally.

Credentials are **plaintext at rest** under an operator-only directory. This is
an accepted limitation, recorded rather than disguised. On this host
`systemd-creds` was measured to provide no real protection — the host key is
absent, the operator lacks TPM access, and every key mode produced output another
identity could decrypt — so an encrypted representation would have claimed a
guarantee the machine cannot deliver. See ADR 0023 for the full tool evaluation.

## Migration status

| Mechanism | State |
| --- | --- |
| `jev` consumer | **Migrated.** First consumer of this standard, live-accepted |
| Grafana metrics | **Compatible.** Materialized and verified through the standard; the existing root-owned `/etc/blaine/secrets/grafana-metrics.env` used by Alloy is unchanged |
| Grafana Cloud OTLP, Fleet | Existing [`infra/grafana-cloud.py`](../infra/grafana-cloud.py) path retained; staged migration, not required by this slice |
| Materialization engine | **Migrated to SecretSpec 0.20.0.** The move reproduced the Jev credential byte for byte; the custom BWS resolver was removed |
| Infrastructure and object-storage secrets | Locally generated rather than Bitwarden-managed; out of scope |
| MIRIX private configuration | Owned by its own checkout; out of scope |

Staged migration is intentional. Nothing was rewritten merely for consistency,
and no working credential path was disturbed to prove the standard.
