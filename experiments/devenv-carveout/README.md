# devenv infrastructure carveout

**Static prototype, not evaluated or started.** Read the
[decision report](../../docs/research/devenv-carveout.md). Process Compose is the
smaller next adoption step for the current host; this single devenv prototype
establishes how the requested topology can be expressed. There is no second
implementation, installation, service takeover or change to production scripts.

## What exists

- `devenv.nix`: five processes, one native-service readiness task, and a small
  registration task reusing `scripts.dev` HTTP helpers. Uses current devenv 2.3
  syntax: native process supervision, `after`, `ready`, `restart`, `shutdown`.
- `devenv.yaml`: Nix input declaration, with no global secret loading.
- `secretspec.toml`: **unprovisioned example** of Keyring → BWS and a MIRIX scope.
  Its nil project UUID and key-name placeholders must be replaced with existing
  non-secret identifiers before use. It contains no secret values.
- `host-observations.json`: read-only executable/readiness inventory.
- `keyring-observations.json`: only attribute names and structural booleans.
- `inspect_host.py`, `inspect_keyring.py`: reproduce those observations without
  service mutations, model calls, secret-value reads, keyring unlocks or writes.
- `validation.json`: static checks only; it is not Nix evaluation evidence.

No Task creation binding was available. This is an unsubmitted work request:
evaluate local process infrastructure, retain bounded evidence and one static
prototype, and stop without changing the host. No durable runtime Task ID or
completion state is claimed.

## Verified prerequisites and missing validation

On 2026-09-19, `devenv`, `nix`, `process-compose` and `secretspec` were absent
from PATH; the conventional Nix executable locations were absent too. `bws
2.1.0` and both existing environment executables were present. PostgreSQL
accepted connections; Redis returned PONG. HTTP health/discovery requests to
the five application ports failed to connect in the observation. No attempt
was made to start them or to reinterpret prior successful MIRIX results.

The first sandboxed socket checks were denied; the retained inventory comes
from the subsequent permitted host read. It does not misclassify a sandbox
denial as a stopped native database.

Only five additional Blaine files were inspected beyond those named in the
request: `scripts/setup-runtime.sh`, ADRs 0003 and 0011,
`runtime/interactive-restate.toml`, and the launch section of
`runtime/interactive.py`. No repository-wide recursive exploration was done.
Narrow reads of the existing MIRIX startup/settings and installed vLLM parser
registries supplied command paths, without changing their environments.

Probe budget: (1) host inventory/readiness, (2) keyring metadata, (3) static
artifact validation. No supervisor, GPU workload, upstream suite or provider
request was executed. The keyring addressing mismatch is the one representative
limitation inspected for that hypothesis; no exhaustive compatibility test.

## Installation commands — documented, NOT executed

Official [Linux setup](https://devenv.sh/getting-started/) currently documents:

```bash
sh <(curl -L https://nixos.org/nix/install) --daemon
nix-env --install --attr devenv -f https://github.com/NixOS/nixpkgs/tarball/nixpkgs-unstable
```

These install software/change the host and require separate approval. No need
to install anything to review this prototype. The inspected documentation is
current as of 2026-09-19, rather than a claim that moving install URLs are pinned.
Require devenv 2.3+ for the shown shutdown options and verify the bundled
SecretSpec version/features. Scopes and CLI-backed BWS need SecretSpec 0.17+;
0.20+ additionally documents forwarding shutdown signals to the target process.
Do not assume the latest standalone SecretSpec documentation exactly matches
whatever version is bundled by a particular devenv package.

After approval and installation, `devenv update` in this directory would resolve
the rolling input and create `devenv.lock`; retain that lock before claiming
repeatable evaluation. No fabricated lockfile is included. Nix evaluation and
runtime validation remain pending; the existing uv environments and model
weights would still be outside Nix's reproducibility guarantees.

## Review before any future start

1. Confirm the host paths in `devenv.nix`. No activation/synchronization of the
   uv environments is necessary: commands use their executable paths directly.
   No CUDA/NVIDIA module or Nix-managed database is enabled. Verify the inherited
   library environment during the first actual run; host ABI/GPU compatibility
   under a Nix shell has not been tested.
2. Confirm launch options against the existing successful serving setup. Model
   IDs, ports, Qwen context and GPU fractions match the request. The Qwen parser
   names exist in the installed vLLM registry, but the complete launch command
   was not reconstructed from an active server and has not been replayed.
3. Resolve the non-secret BWS project/key identifiers and obtain approval for
   any necessary credential bootstrap. Do not place values in this file, Nix
   expressions, the parent shell, or plaintext `.env` files. No `dotenv` provider
   or automatic missing-secret prompt is configured.
4. Arrange ownership handoff from manual/existing supervisors before starting
   these same ports. Do not run `scripts/dev-up.sh` concurrently or kill unknown
   listeners. The prototype reuses the existing Restate configuration/data path;
   a future run is a real service start, not a disposable data simulation.

The MIRIX checkpoint's persisted Qwen/BGE configuration remains authoritative
for this experiment. Starting its HTTP server does not reinitialize agents,
rewrite model endpoints, create another Qwen instance for Goose, or migrate a
database. `MIRIX_PG_URI`/`MIRIX_REDIS_URI` declarations illustrate existing
settings; mapping the actual BWS keys to those values remains unverified.

## Native developer interface — future commands, not executed

From this directory, once prerequisites and ownership are settled:

```bash
devenv up -d --mode all                  # five services plus downstream registration
devenv processes list                    # status of all managed processes
devenv processes status mirix
devenv processes logs mirix --lines 100  # snapshot; attach for live status/logs
devenv processes attach
devenv processes restart mirix
devenv up -d --mode all blaine-runtime  # Restate dependency and registration; no GPU stack
devenv up -d mirix                     # MIRIX plus native check, Qwen and BGE dependencies
devenv down
```

Subset commands describe dependency scheduling from a new manager; attaching to
an existing manager uses its original configuration. Config edits require a
manager restart. `up` normally follows upstream dependencies; `--mode all` also
includes the downstream `blaine:register` task. The explicit task command is
`devenv tasks run blaine:register` when registration is needed separately.

Registration still only ensures the existing URI is present, like the current
spike. Revision/deployment verification remains Blaine-specific. Existing
`dev.py doctor/status` require its PID records and therefore cannot be used
unchanged against devenv-owned processes. No aesthetics-only CLI wrapper is
proposed.

Readiness checks: native `pg_isready` + Redis PING gate MIRIX startup; vLLM
`/health`; MIRIX `/health`; Restate `/deployments`; runtime `/discover` with a
manifest Accept header. These are stronger than a timer or PID check, but do
not prove schema/extension readiness, inference quality or durable Task success.
MIRIX's health handler is shallow. The one-shot native check does not monitor a
later database outage or provide automatic dependency restart cascades.

## Secret bootstrap decision

[SecretSpec keyring](https://secretspec.dev/providers/keyring/) addresses entries
by service and account; `ref.item`/`ref.field` can address compatible existing
entries. The observed BWS candidates instead have attributes `service`,
`credential`, `xdg:schema`, with no `user`/`username`. Direct reuse of those
entries is **not established**; changing the service name alone is insufficient.
Do not rewrite the existing entries or add an adapter in this carveout.

With approval, the conventional bootstrap for this manifest would be:

```bash
secretspec --file secretspec.toml config provider login bitwarden
```

This prompts for and **writes** the access token to the configured keyring
provider; it was not run. It would create the conventional
`secretspec/blaine-local/default/access_token` service under the current account.
GNOME session unlock/YubiKey enforcement stays with the existing host; neither
devenv nor SecretSpec establishes that human-authentication link.

MIRIX is the only process launched through `secretspec run --scope mirix`.
The BWS token is a provider credential, not an application-secret declaration.
The official provider passes it to the `bws` child environment; selected
application secrets then reach the MIRIX child. This minimizes delivery, not
same-user access: scopes are not OS authorization, and arbitrary inherited
environment values/app logging are not automatically made safe. No global
`secretspec.enable`, `config.secretspec.secrets`, `export` or plaintext cache is
used. Process Compose can use this same standalone SecretSpec command.
