# Secret-delivery correction spike

Reopens three questions the [secret-delivery ADR](../../docs/decisions/0023-runtime-secret-delivery-and-materialization.md)
answered too early: what produced the desktop authentication prompts, whether
SecretSpec should own provider resolution, and whether plaintext at rest is the
right local representation. **No engine decision is made here.**

The working Jev integration and its live authenticated evidence are unchanged.

## 1. Authentication-prompt audit

[authentication-audit.json](evidence/authentication-audit.json)

| Prompt source | Triggering operation | Expected? | Required for materialization? | Required for runtime? |
| --- | --- | --- | --- | --- |
| polkit, dialog drawn by `gnome-shell` | unprivileged `systemd-creds` during the at-rest tool evaluation | **No** | No | No |
| GDM `gkr-pam` login keyring unlock | operator desktop login or screen unlock | Yes | Only if the keyring is locked when materializing | No |
| `sudo` | read-only inspection of root-owned files, non-interactive `sudo -n` | Yes | No | No |

systemd 259 runs unprivileged `systemd-creds` through privileged
`systemd-creds@N-….service` helper units, each authorized by polkit. Eight such
units appear between 21:27:47 and 21:29:23, matching the evaluation's eight
invocations one for one. Nothing attributes a prompt to Bitwarden, to `bws`, to
`secret-tool` or to materialization: the 21:30–21:36 materialization window
contains zero authentication events.

**Host side effect, reported not repaired.** `/var/lib/systemd/credential.secret`
did not exist before the evaluation and was created at 21:27 (root:root, 0400)
after an operator polkit authentication. It is the standard systemd host key and
was left in place for the operator to decide on, not removed unilaterally.

**Correction.** The earlier reading — identical output across key modes, root able
to decrypt, therefore nominal encryption — was wrong. The host key was created
during the test and really was used; root could decrypt because root owns that
key file. The accurate disqualifier is stronger: unprivileged `systemd-creds`
needs polkit, so a systemd **user** service could not decrypt without an
interactive desktop prompt, which the runtime requirement forbids outright.

## 2. SecretSpec live spike

[secretspec-spike.json](evidence/secretspec-spike.json) — stable **0.20.0**,
published 2026-08-31, downloaded with its published SHA-256 verified and
extracted to a scratch directory only. The host was not modified.

All ten spike requirements passed, including live BWS resolution against the real
project, resolution of the declared secret only, fail-closed behaviour with no
bootstrap token, and a composition where `secretspec export` feeds Blaine's
existing validation and atomic `0600` activation to produce a credential
identical to the one already in use.

Two properties are worth naming. The BWS provider accepts `BWS_ACCESS_TOKEN` from
the environment, so the existing keyring bootstrap feeds it unchanged — no
keyring migration and no `secretspec config provider login`. And 0.20 defaults
`require_reason` to `"agents"`: an agent-driven resolution is refused unless it
states a reason, which is then written to a local audit log.

The rejected model — service startup resolving through SecretSpec to BWS — was
never tested as an adoption candidate and remains rejected.

## 3. Phased acceptance of the current materializer

[phased-acceptance.json](evidence/phased-acceptance.json) — **PASS**, with zero
interactive authentication events in every phase.

| Phase | Result |
| --- | --- |
| A — explicit materialization | Succeeded; no operator authentication requested, because the login keyring was already unlocked |
| B — verify local material | `0600`, owner-only, exactly the declared key, available through the runtime boundary without contacting the secret manager |
| C — runtime restart without the secret manager | Consumer exited 0 with `secret-tool`, `bws`, `secretspec`, `systemd-creds`, `pkexec` and `sudo` all replaced by failing shims; no blocked tool invoked, no bootstrap leaked |
| D — session independence | Consumer succeeded with no `DISPLAY`, `DBUS_SESSION_BUS_ADDRESS`, `XDG_SESSION_ID`, `WAYLAND_DISPLAY` or `SSH_AUTH_SOCK` inherited |

Phase A's silence is conditional, not structural: materialization *would* raise a
keyring unlock prompt if the keyring were locked. That is the one deliberate,
bounded interactive boundary, and it disappears once materialization is done.

## 4. Jev revalidation

Re-run through the accepted path: `AUTHENTICATED` against `jev-1.13.0`, 372 ms,
431 input and 49 output tokens, candidate suitability recorded and not applied to
routing. Zero interactive authentication events during the run, and the provider
source contains zero references to Bitwarden, the keyring, `secret-tool` or
SecretSpec.

## What this spike deliberately does not do

It selects no materialization engine, changes no consumer, replaces no working
credential, installs nothing on the host, and modifies no service. The engine
choice is an open question for the operator.
