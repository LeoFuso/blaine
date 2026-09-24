# ADR 0023 — Runtime Secret Delivery and Materialization

**Status:** Accepted  
**Validation:** Integration — first consumer materialized and accepted live, engine selected by the operator after a live comparison

## Context

Blaine needs externally managed API credentials while remaining independently
bootable and restartable. Until now each credential grew its own path: the
Grafana Cloud materializer reads Bitwarden through a GNOME Keyring bootstrap and
writes a root-only environment file, infrastructure secrets are generated locally,
and the rootless migration copied its own private files. Nothing stated where a
remote secret manager may appear in a lifecycle.

Making a service reach Bitwarden or the keyring at startup would couple normal
operation to remote availability, to an unlocked interactive session, and to far
more credential authority than any one consumer needs. That contradicts the
accepted requirement that the host boots, starts user services through linger and
restarts them without an interactive login.

The isolated Jev provider exposed this concretely. An agent finishing the
integration needed `TYPESAFE_API_KEY`, and its attempt to read the credential
store was correctly blocked as credential exploration. The right conclusion was
not to widen the agent's permissions but to notice that a provider should never
have had authority over the secret manager in the first place.

## Decision

Bitwarden Secrets Manager is the source of truth for managed Blaine secrets and
is **not** a runtime dependency. GNOME Keyring holds only the bootstrap machine
credential and is **not** a runtime dependency either.

```text
Bitwarden Secrets Manager
    | only during explicit materialization or rotation
    v
local materializer (operator-invoked)
    v
local consumer-specific credential
    v
systemd service or bounded process
    v
runtime
```

The invariants are:

- Remote secret-manager access happens only during explicit provisioning,
  materialization or rotation. Machine boot, linger startup, service restart,
  provider invocation and Task execution never reach it.
- Git holds declarations — required key, consumer, destination, constraints —
  and never values.
- A consumer receives only the secrets declared for it. The whole project is
  never exported into one environment, and authority over the secret manager is
  withheld from consumers even when an operator shell exports it.
- Materialization replaces a credential atomically, or leaves the previous valid
  credential untouched.
- Runtime credential material is readable only by the intended identity.
- Rotation is an explicit operator action, never a reboot and never an automatic
  restart of unrelated services.

The local at-rest representation is an operator-owned `0600` environment file
under `~/.config/blaine/secrets/<consumer>.env`, reusing the location the
rootless migration already established.

**Provider resolution is SecretSpec's; the rest is Blaine's.** The operator
selected this split after a live comparison. SecretSpec 0.20.0, pinned by digest,
resolves declared secrets from whatever backend sits behind a single
`runtime_secrets` alias. Blaine keeps the consumer allowlist, the destination,
restrictive atomic activation, verification, bootstrap withholding and rotation
reporting. `infra/secrets.py` is that wrapper; it is not a secret-management
server, adds no daemon, and implements no cryptography.

Each consumer owns a separate SecretSpec manifest. Profiles were measured to
**extend** the default profile rather than isolate from it, so a shared manifest
would let one consumer resolve another's secrets; separate manifests plus
Blaine's own allowlist keep least-secret delivery true rather than assumed.

**Rotation does not reload.** A process that has already started holds its value
in its environment. Materialization reports whether the value changed and whether
a declared service must be restarted; it restarts nothing itself.

### Tools evaluated

| Tool | Version / state | Outcome |
| --- | --- | --- |
| `bws` | 2.1.0, installed and already proven by the Grafana path | **Adopted** as the remote client, used only at materialization time |
| GNOME Keyring | existing operator convention | **Retained** for the bootstrap credential only; never materialized to a consumer |
| systemd credentials | systemd 259 with `systemd-creds` present | **Rejected — corrected rationale.** The original reading, that its encryption was nominal, was wrong: the host key was created during the test and really was used. The accurate disqualifier is that unprivileged `systemd-creds` requires polkit authorization on this host, so a systemd user service could not decrypt without an interactive desktop prompt. See the [correction spike](../../experiments/secret-delivery-spike/README.md) |
| SecretSpec | **0.20.0 stable, live-spiked, adopted** | **Adopted as the resolver.** A live spike passed all ten requirements, including BWS resolution through the existing keyring bootstrap with no keyring migration, resolution limited to declared secrets, fail-closed behaviour, and composition with this ADR's atomic activation producing a byte-identical credential. Its default refusal of agent-driven access without a recorded reason addresses the boundary that prompted this work |
| SOPS / age | absent from the host | **Deferred.** Real at-rest encryption needs a key that must itself be readable non-interactively at boot, which reduces to the same local trust boundary while adding key distribution |

A `0600` file was therefore selected because the alternatives on this host either
require an interactive prompt the runtime forbids or move the same trust boundary
somewhere less obvious. That is a limitation recorded honestly, not a security
claim.

### Provider portability, and where it stops

Substituting the backend behind the alias was proven live: swapping Bitwarden for
a synthetic local backend changed the resolved value while the Jev provider
source, the consumer declaration, the wrapper source and the manifest stayed
byte-identical, with a one-line configuration delta. `awssm`, `vault` and
`openbao` are built in and occupy the same alias.

The boundary is addressing, and it lands in declarations rather than code. Vault
and OpenBao carry mount and path in the alias URI and need only a token bootstrap
change, which is **inferred** from the accepted URI grammar rather than
live-tested. AWS Secrets Manager refuses a path and demands a per-secret `ref`,
which is itself backend-coupling: a manifest carrying one stopped resolving
against another backend. No Blaine source change is required for any of them.

## Consequences

Services and bounded processes start from local credentials alone, so Bitwarden
downtime, a locked keyring, an absent session or missing internet access cannot
prevent a restart. A compromised consumer exposes only its own declared secrets.

The cost is that a rotated remote secret does not reach a consumer until an
operator materializes it: staleness is now an explicit operational state rather
than an invisible one. Credentials remain plaintext at rest under an operator-only
directory, which is the residual risk this decision accepts. Multi-host operation
would need materialization on each host.

Adding a secret means declaring it, materializing its consumer and verifying;
removing one means deleting the declaration and the local credential. Adopting
this for the remaining legacy mechanisms is staged, not required at once.

## Validation

### Hypothesis

A consumer can obtain its credential and run with the secret manager and the
keyring entirely unavailable, while receiving no other consumer's secrets and no
authority over the secret manager.

### Validation level

`Integration`.

### Minimal validation

Materialize one real consumer, then launch it with `secret-tool` and `bws`
replaced by shims that fail, with another consumer's secret and a bootstrap token
present in the inherited environment.

### Evidence

[Acceptance report](../../infra/validation-secret-delivery.json) and the
[four-phase acceptance](../../experiments/secret-delivery-spike/evidence/phased-acceptance.json):
the Jev consumer started with exit code 0, its declared credential present and
non-empty, no secret-manager invocation, no bootstrap token, no other consumer's
secret, and no interactive authentication event in any phase. The first run of
this acceptance **failed** and exposed a real defect — an inherited
`BWS_ACCESS_TOKEN` reached the consumer — which was fixed before the pass.

Migrating the engine to SecretSpec reproduced the credential byte for byte
(`outcome: unchanged`), and the Jev provider re-authenticated against
`jev-1.13.0` afterwards with zero authentication prompts. The same standard also
materialized and verified the already-proven Grafana metrics consumer without
touching its existing root-owned credential.

### Not required for validation

A secret-management server, Vault or OpenBao, encrypted at-rest material, a
long-lived daemon, migration of every existing credential, systemd unit changes,
a host reboot, or any change to the Personal Agent Hub work.

## Reconsider when

Multiple hosts make manual materialization operationally insufficient; a cloud
deployment requires dynamic short-lived credentials; a broker such as Vault or
OpenBao becomes justified by real multi-consumer demand; or systemd credentials
become genuinely host-bound on this machine, in which case the local
representation can improve without changing the lifecycle this ADR fixes.
