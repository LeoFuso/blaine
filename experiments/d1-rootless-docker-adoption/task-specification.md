You are continuing Blaine D1 — Long-Lived Platform Runtime on the actual Blaine
workstation.

This is a real host migration, not a hypothetical design exercise.

Work autonomously and carry the task as far as safely possible. Inspect the
repository and current machine state before modifying anything. Do not blindly
trust this prompt where current observable state disagrees with it.

MODEL/WORK STYLE

- This is a careful infrastructure migration.
- Prefer evidence and reversible changes over cleverness.
- Do not stop merely to ask the human to choose among equivalent implementation
  details; inspect the existing architecture and make the most conservative
  coherent choice.
- STOP only at an actual safety boundary, missing authorization, destructive
  ambiguity, or failed acceptance condition.
- Never claim PASS without evidence.

CURRENT REPOSITORY / PROGRAM CONTEXT

Repository:
  ~/workspace/blaine

D1 is IN PROGRESS.

The infrastructure foundation has already been implemented:
- Docker / Compose
- SeaweedFS object storage
- ClickHouse
- Langfuse Web
- Langfuse Worker
- native PostgreSQL 18
- native Redis
- native Grafana Alloy
- Ansible desired-state material

Backup remains PAUSED.
Do not resume backup work.

Full D1.G is NOT complete because Blaine, Restate, vLLM and MIRIX service
adoption remains pending.

An ADR for the local inference baseline was already committed on the current
development branch:

  commit 74b2993
  docs: define D1 local inference baseline

Do not rewrite that history and do not reopen the model-selection discussion.
Inference adoption is not the task here.

IMPORTANT OBSERVED HOST STATE

A real infrastructure-only host reboot was performed on 2026-09-21.

Before boot ID:
  55f6e9ad-7915-472d-aaf5-7c9d689c3747

After boot ID:
  4e64cd04-43eb-45ef-b493-15fb67cc8072

After reboot, without manually starting services:

  docker.service                   active
  blaine-infra.service             active
  alloy.service                    active
  postgresql@18-main.service       active
  redis-server.service             active

systemctl --failed:
  zero failed units

The following recovered healthy:
- SeaweedFS
- ClickHouse
- Langfuse Web
- Langfuse Worker
- Alloy
- PostgreSQL
- Redis

Therefore:
  infrastructure-foundation full-host reboot recovery = PASS

This does NOT mean D1.G PASS.

ROOTFUL DOCKER CURRENT STATE

The existing production-like Blaine infrastructure is still running under the
system/rootful Docker daemon.

System daemon:
  /var/run/docker.sock
  system docker.service

The current rootful Compose stack is healthy.

Existing root unit:
  /etc/systemd/system/blaine-infra.service

It currently owns the rootful Compose stack.

Do not stop or alter the healthy rootful stack until a rootless candidate has
been proven and a deliberate cutover point has been reached.

ROOTLESS DOCKER CURRENT STATE

Rootless prerequisites are installed:

  docker-ce-rootless-extras 29.8.1
  uidmap

Subordinate mappings exist:

  leofuso:100000:65536

in both /etc/subuid and /etc/subgid.

A rootless Docker daemon has already been successfully installed.

User service:

  ~/.config/systemd/user/docker.service

Observed:

  systemctl --user status docker.service
  => active (running), enabled

Rootless socket:

  /run/user/1000/docker.sock

Docker contexts:

  default
    unix:///var/run/docker.sock

  rootless
    unix:///run/user/1000/docker.sock

Current Docker CLI context:
  rootless

Rootless SecurityOptions include:
  name=rootless

A rootless `docker run --rm hello-world` has already passed.

Therefore:
  basic rootless Docker runtime = PASS

Linger has NOT yet been deliberately accepted as complete.
Inspect before changing.

OPERATOR / PRIVILEGE DECISION

A previous attempt added `leofuso` to the rootful `docker` group in order to use
Docker without sudo.

That revealed the architectural problem:

  access to the rootful Docker socket is effectively root-equivalent.

That is NOT the desired Blaine operating model.

The intended direction is:

  root
    host provisioning / true machine administration only

  leofuso
    normal Blaine operator
    rootless Docker
    systemd --user services
    normal Blaine operation WITHOUT sudo

The final operational Blaine runtime must not require membership in the rootful
docker group.

Do not solve permissions by broadening rootful Docker access.

Do not add NOPASSWD rules.
Do not modify sudoers.

SUDO RULE

You may test:

  sudo -n true

If it succeeds, sudo is temporarily authorized for bounded host-bootstrap or
cutover operations that are clearly necessary for this migration.

If `sudo -n true` fails:

- do NOT attempt interactive password prompting;
- do NOT weaken permissions;
- do NOT modify sudoers;
- continue all work possible without root;
- prepare an exact minimal root-action script or command block;
- STOP only when execution genuinely depends on those commands.

CURRENT /etc/blaine STATE

Observed:

  /etc/blaine
    root:docker 0750

  /etc/blaine/infra
    root:docker 0750

  /etc/blaine/infra/compose.yaml
    root:docker 0640

  /etc/blaine/infra/alloy-local.alloy
    root:docker 0640

  /etc/blaine/infra/cloud.alloy.inactive
    root:docker 0640

Secrets remain protected:

  /etc/blaine/secrets
    root:root 0700

  /etc/blaine/secrets/clickhouse.env
    root:root 0600

  /etc/blaine/secrets/infrastructure.json
    root:root 0600

  /etc/blaine/secrets/langfuse.env
    root:root 0600

  /etc/blaine/secrets/object-storage.json
    leofuso:leofuso 0400
    but parent directory is root-only

  /etc/blaine/backup.json
    root:root 0600

No secret value may be printed, logged, copied into Git, or exposed by broader
permissions.

The root:docker permission experiment should NOT become the final operational
architecture.

ARCHITECTURAL DECISION TO IMPLEMENT

Migrate Blaine's containerized infrastructure from rootful system Docker to
rootless Docker owned by the normal Blaine operator.

The desired end state is approximately:

  machine boot
      |
      +-- user@1000.service via linger
              |
              +-- rootless docker.service
              |
              +-- rootless blaine-infra.service
                      |
                      +-- SeaweedFS
                      +-- ClickHouse
                      +-- Langfuse Web
                      +-- Langfuse Worker

Normal operations:

  docker ps
  docker compose ...
  systemctl --user ...

must not require sudo.

Root should only be needed for genuine host/bootstrap operations.

The rootful Docker daemon must no longer be required by Blaine after accepted
cutover.

Do not disable or remove the rootful Docker daemon unless:
- no unrelated rootful Docker workloads exist;
- the rootless Blaine stack has passed acceptance;
- rollback remains understood.

Do not uninstall Docker.

CONFIG / SECRET OWNERSHIP

Do NOT make root-only secrets docker-group readable.

For the rootless runtime, choose a coherent user-owned operational config and
secret layout based on the existing repository conventions.

Preferred principles:

- Git repository remains the versioned source of truth for non-secret desired
  state.
- Materialized runtime config may live in a stable user-owned location such as
  ~/.config/blaine or an explicitly operator-owned /srv/blaine subtree.
- Runtime secrets are external to Git.
- Secret directories: 0700.
- Secret files: 0600 or stricter.
- Only the rootless service identity/operator should need to read them.
- /etc/blaine may remain for root-owned host/bootstrap material if still useful,
  but should not be required for ordinary rootless operation.

Inspect existing runbooks and Ansible before choosing exact paths.

PERSISTENT DATA SAFETY

This is critical.

Existing persistent data includes at least:
- SeaweedFS metadata/filer/volumes
- ClickHouse data
- Langfuse dependencies/data relationships
- relevant /srv/blaine/infra paths

Rootless user namespaces change UID/GID mapping.

Do NOT assume existing rootful bind mounts are writable by rootless containers.

Before any data ownership change:

1. inventory exact Compose mounts;
2. inventory host ownership/modes;
3. inspect container effective users;
4. understand rootless UID/GID mapping;
5. test compatibility against scratch/candidate storage where possible.

Never destructively chown live persistent data just to see if it works.

Prefer:
- isolated candidate storage;
- copy/migration with rollback;
- explicit validation;
- final cutover only after compatibility is proven.

Do not delete historical data.

Do not touch /srv/blaine-backup except read-only inspection if absolutely
necessary.

Backup remains PAUSED.

NETWORKING

Inspect the current Compose topology carefully.

Langfuse may currently use host networking.

Do not assume rootful `network_mode: host` semantics are identical under
rootless Docker.

Verify behavior empirically.

If rootless host networking is not appropriate, prefer explicit localhost
published ports while preserving the existing private-host semantics.

No public exposure is required for private v0.

Do not introduce Caddy/public ingress as a prerequisite.

DOCKER CONTEXT SAFETY

Before every destructive or state-changing Docker operation, explicitly verify
which daemon is being targeted.

Prefer explicit commands:

  docker --context rootless ...

and, when observing the legacy daemon:

  docker --context default ...

Do not rely on an implicit current context during migration.

Use a distinct candidate Compose project name while both daemons coexist.

Do not accidentally start a second stack binding the same host ports.

MIGRATION WORKFLOW

Carry out the following as an evidence-driven migration, adapting details to the
actual repository and host.

1. Inspect repository state.
   - git status
   - current branch
   - existing ADRs
   - D1 roadmap
   - platform infrastructure/runbook docs
   - Ansible
   - Compose
   - systemd units
   - validation/evidence conventions
   - relevant AGENTS.md instructions

2. Inspect actual host state.
   - rootful Docker
   - rootless Docker
   - containers
   - ports
   - systemd system and user services
   - storage mounts
   - ownership
   - secrets metadata WITHOUT printing values
   - subuid/subgid
   - linger state

3. Record sanitized pre-migration evidence under an appropriate location such as:

     experiments/d1-rootless-docker-adoption/evidence/

   Do not store secrets.

4. Design the smallest rootless-compatible change.

5. Update the repository so the chosen rootless model becomes explicit desired
   state rather than undocumented machine state.

6. Update Ansible or equivalent provisioning material so a future convergence
   does not silently recreate the old rootful-only operating model.

7. Do not blindly encode the current temporary root:docker permission experiment
   into desired state.

8. Prepare rootless runtime config and secret materialization.

9. Validate a rootless candidate without disrupting the current healthy stack.
   Use alternate project names, ports and/or scratch state as necessary.

10. Exercise:
    - SeaweedFS
    - ClickHouse
    - Langfuse Web
    - Langfuse Worker
    - their health/readiness behavior
    - persistent storage semantics

11. If a candidate cannot faithfully preserve the required behavior, STOP and
    report the exact blocker. Do not force a cutover.

12. If candidate PASS is strong enough, plan a bounded cutover.

13. At cutover:
    - capture final rootful state;
    - stop only the Blaine rootful stack as necessary;
    - preserve/copy state coherently;
    - start rootless stack;
    - validate every service;
    - validate data identity/content where existing D1 evidence supports it.

14. Establish rootless user service ownership for the stack.

    Desired operational controls should be of the form:

      systemctl --user status docker
      systemctl --user status blaine-infra

15. Enable appropriate user-manager boot persistence using linger if required.

16. Only after rootless acceptance:
    - disable the old root-owned blaine-infra service;
    - ensure it cannot start a duplicate stack;
    - remove operational dependence on /var/run/docker.sock;
    - remove `leofuso` from the rootful docker group when safely possible;
    - document that a new login/session may be needed before supplemental group
      membership disappears.

17. Do NOT reboot automatically.

A new reboot is a separate human-authorized acceptance action.

At the end, leave the machine ready for that reboot and state exactly what still
needs human authorization.

ROOTFUL DOCKER

If no unrelated rootful workloads exist after migration, it is acceptable to
prepare the system rootful Docker service for disablement, but do not make an
unsafe assumption.

Inventory first.

If disabling rootful Docker is not required to close the Blaine migration,
prefer leaving the package installed but clearly unused by Blaine.

REPOSITORY DOCUMENTATION

Update the repository to reflect BOTH the decisions and the actual evidence.

At minimum inspect and update as appropriate:

- docs/platform-infrastructure.md
- docs/platform-operations.md
- docs/platform-d1.md
- docs/roadmap/001-blaine-development-roadmap.md
- docs/decisions/README.md
- ADR 0018 if it contains superseded assumptions
- infra/validation-d1-infrastructure.json
- Ansible files
- Compose/systemd desired-state files
- README/navigation if needed

Create a new ADR if the rootless operating model materially changes a previously
accepted architecture. Use the next available ADR number after inspecting the
repo; do not assume a number.

The ADR should record at least:

- rootful Docker group access was considered;
- it was rejected as the long-lived operator model because access to the rootful
  daemon is root-equivalent;
- rootless Docker was selected so normal Blaine operations do not require root;
- root remains necessary only for bounded host/bootstrap administration;
- user systemd + linger is the intended boot model;
- secrets remain external and user-scoped;
- persistent-data UID/GID migration implications;
- rollback / reconsideration conditions.

Update D1 status carefully.

Record:

  infrastructure foundation reboot acceptance = PASS

because a real new boot identity was observed and infrastructure recovered
automatically.

Do NOT claim:

  D1.G PASS

because Blaine, Restate, vLLM and MIRIX service/recovery adoption remains
pending.

Record the rootless Docker migration's actual state accurately:
- IN PROGRESS,
- PASS,
- or STOP,
based strictly on evidence.

INFERENCE DECISION

Preserve the already-created local inference ADR.

Do not install or benchmark Qwen during this task.

D1.C resumes only after the platform/rootless work is stable.

VALIDATION

Run all repository validation that is appropriate, including:

- git diff --check
- relevant tests
- Ansible syntax validation
- scratch/dry-run convergence where supported
- second-run/idempotency checks where supported
- Compose config validation
- systemd unit verification
- documentation/link consistency where tooling exists

For live infrastructure evidence, verify at minimum:

- rootless Docker SecurityOptions contains rootless;
- rootless Docker works without sudo;
- rootless Compose works without sudo;
- every required container is healthy;
- ClickHouse responds;
- SeaweedFS responds and preserves expected object identity/content;
- Langfuse Web responds;
- Langfuse Worker responds;
- PostgreSQL remains healthy;
- Redis remains healthy;
- Alloy remains healthy;
- controlled rootless Docker restart succeeds;
- controlled rootless Blaine stack restart succeeds;
- no rootful duplicate stack is hiding a failure.

Do not claim reboot recovery for the rootless topology until an actual later
human-authorized reboot is performed.

SECURITY / HARD STOP RULES

NEVER:

- print secret contents;
- commit secrets;
- broaden secret permissions merely to make Compose convenient;
- add NOPASSWD;
- modify sudoers;
- run the Codex process itself as root;
- use the rootful docker group as the final Blaine operator model;
- delete persistent data;
- overwrite historical backups;
- unpause backup;
- reboot the machine;
- change the selected inference architecture;
- push to origin without explicit human authorization;
- rewrite Git history.

If a migration step requires a risky in-place ownership transformation with no
proven rollback, STOP.

If a root command is required and `sudo -n true` is unavailable, produce a
minimal executable/root-action command list and STOP at that boundary rather
than weakening security.

GIT

Preserve current work.

Do not reset or rewrite the existing ADR 0019 commit.

Make coherent local commits when the work reaches defensible milestones.

Do not push.

FINAL REPORT

At completion, provide a concise report containing:

- PASS / STOP status;
- final rootless topology;
- what changed on the host;
- what changed in Git;
- commits created;
- validation evidence;
- whether rootful Docker is still running/required;
- whether `leofuso` is still in the rootful docker group;
- exact remaining root/human action, if any;
- exact remaining reboot acceptance step;
- any limitations that prevent calling this migration complete.

The goal is not merely to make Docker commands work.

The goal is to leave Blaine with a boring, reproducible, documented,
non-root operational container runtime that can later survive a final D1 reboot
acceptance.
