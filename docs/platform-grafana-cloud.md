# Grafana Cloud activation runbook

Preparation: **COMPLETE**. Runtime: **CONFIGURED FOR FUTURE ACTIVATION**.
No Grafana Cloud account/stack exists for this D1 pass; Bitwarden was observed
unauthenticated. No remote exporter is active or remote delivery claimed. Local
Alloy works without cloud credentials or an unlocked vault.

This is the future operator procedure from that starting point to the first
synthetic telemetry visible in Grafana Cloud. The authentication, activation and
smoke commands below were **not executed** to close the preparation item. Run them
in one local Bash terminal as the normal operator. Stop at any failed command;
continue only after its expected result is established. No reboot, session restart,
Docker group membership or temporary sudoers rule is needed.

## 1. Check the local prerequisites

```sh
cd /home/leofuso/workspace/blaine-platform-d1
export PATH="$HOME/.local/bin:$PATH"
set +x
bw --version
test -r /usr/local/lib/blaine/grafana-cloud.py
test -r infra/smoke-otlp.py
systemctl is-active alloy
curl --fail --silent --show-error http://127.0.0.1:12345/-/healthy
python3 /usr/local/lib/blaine/grafana-cloud.py status
```

Expected: CLI available (D1 installed 2026.9.0), files present, Alloy `active`, HTTP
success, and Bitwarden `unauthenticated`. The helper prints only authentication
state. These checks do not authenticate or enable export. Keep shell tracing off
throughout credential handling; never put credential values in commands or Git.

## 2. Create the Grafana Cloud account and stack

Open [Grafana Cloud signup](https://grafana.com/auth/sign-up/create-user) in a
browser, create the account, and complete its verification prompts. In the
[Cloud Portal](https://grafana.com/profile/org), select the account and its initial
stack, or choose **Create stack** if onboarding did not create one. Choose a stack
name and region, wait for provisioning, and open its Grafana instance. Retain the
stack URL for the later Explore checks.

In the Cloud Portal select the same stack. Under **Manage your stack**, choose
**OpenTelemetry → Configure**. The stack's OpenTelemetry connection/setup page
also exposes these connection details. Copy:

- The **OTLP HTTP base endpoint**, including `/otlp`. Do not use the Grafana UI URL
  or append `/v1/traces` to this base value.
- The **OTLP instance ID / username from that same page**. Do not infer it from an
  email, organization ID or unrelated metrics instance.

See the official [Cloud Portal guide](https://grafana.com/docs/grafana-cloud/platform/security-and-account-management/account-management/cloud-portal/)
and [OpenTelemetry connection-details guide](https://grafana.com/docs/grafana-cloud/observe-and-act/agent-observability/get-started/grafana-cloud/).

## 3. Create the scoped ingestion token

Use the connection UI's token-generation flow, or open **Cloud access policies**
in the stack's Administration settings. Create policy `blaine-otlp-write`, select
only `metrics:write`, `logs:write`, and `traces:write`, then add a token with a useful
expiry. Record who will rotate it. The stack UI scopes the policy to that stack;
if using the Cloud Portal policy screen, explicitly select the **stack** realm
and this stack rather than the organization-wide realm.

This must be a **Cloud Access Policy token**. A Grafana service-account token for
the dashboard HTTP API is a different credential. Keep the one-time token display
open until saved in Bitwarden; do not put it in shell arguments, screenshots or
this conversation. Official [access-policy concepts](https://grafana.com/docs/grafana-cloud/platform/security-and-account-management/security-and-access/authentication-and-permissions/access-policies/)
and [three-signal write scopes](https://grafana.com/docs/grafana-cloud/observe-and-act/agent-observability/get-started/grafana-cloud/)
define these permissions.

## 4. Authenticate and unlock Bitwarden locally

While the CLI is unauthenticated, select the server owning the operator's account.
Run **one** applicable command:

```sh
bw config server https://vault.bitwarden.com  # US-hosted account
# OR, for an EU-hosted account:
bw config server https://vault.bitwarden.eu
# For self-hosting, use the operator's actual existing vault URL instead.
```

If no Bitwarden account exists, create one in the selected server's browser UI
first. An existing account must use its existing region; configuring the CLI
server does not migrate a vault.

Answer login, master-password and two-step-login prompts only in the local
terminal. Capture raw session output so the session key is not displayed:

```sh
BW_SESSION="$(bw login --raw)" && export BW_SESSION
python3 /usr/local/lib/blaine/grafana-cloud.py status
```

Expected: `unlocked`. If the initial status was already `locked`, use this instead
of logging in again:

```sh
BW_SESSION="$(bw unlock --raw)" && export BW_SESSION
python3 /usr/local/lib/blaine/grafana-cloud.py status
```

`BW_SESSION` remains only in this operator shell environment. Never persist it in
a profile, file, Git or systemd. Never ask another person to send the master
password or session key. The [official Bitwarden CLI guide](https://bitwarden.com/help/cli/)
covers authentication, unlocking and raw output.

## 5. Populate exactly the intended Bitwarden item

Only after the helper reports `unlocked`:

```sh
python3 /usr/local/lib/blaine/grafana-cloud.py placeholder
```

This creates a secure note only when the named item is absent; an existing item
is left unchanged. It neither enumerates nor dumps the vault. In the Bitwarden UI,
open exactly **Blaine / Grafana Cloud** and populate these custom fields:

| Field | Initial placeholder → final value |
|---|---|
| `GRAFANA_CLOUD_OTLP_ENDPOINT` | `REPLACE_ME_NOT_ACTIVE` → actual HTTPS OTLP base endpoint |
| `GRAFANA_CLOUD_OTLP_USERNAME` | `REPLACE_ME_NOT_ACTIVE` → numeric OTLP instance identifier |
| `GRAFANA_CLOUD_OTLP_API_KEY` | `REPLACE_ME_NOT_ACTIVE` → scoped token; use a hidden field |

If the helper cannot establish item absence, create a **Secure note** manually
with that exact name and fields. Do not create duplicates or replace unrelated
credential items. Save all three real values, close the token display, clear any
copied token from the clipboard, and sync the CLI:

```sh
bw sync
```

Expected: sync succeeds. Do not inspect using a bare `bw get item`, since that
prints secret fields. The materialization helper captures the selected item.

## 6. Materialize the runtime environment and lock the vault

```sh
sudo -v
if python3 /usr/local/lib/blaine/grafana-cloud.py materialize; then
  printf '%s\n' 'Materialization succeeded; activation remains a separate step.'
else
  printf '%s\n' 'Materialization FAILED: stop here; do not activate.'
fi
bw lock
unset BW_SESSION
python3 /usr/local/lib/blaine/grafana-cloud.py status
```

Proceed only if materialization succeeded. Expected final vault status: `locked`.
The helper captures only the selected item, validates the three fields, and sends
only those fields over stdin to its bounded root writer. `BW_SESSION` is not sent
to systemd or written to disk. This is an explicit operator action; there is no
Bitwarden background synchronization daemon or runtime unlock dependency.

Verify file metadata without displaying its contents:

```sh
sudo stat -c '%U:%G %a %n' /etc/blaine/secrets/grafana-cloud.env
```

Expected: `root:root 600 /etc/blaine/secrets/grafana-cloud.env`. Its parent is
root-only 0700, outside Git. Do not `cat`/`source` it or include it in diagnostics.
Materialization does **not** enable export.

The current validator accepts an HTTPS hostname ending `.grafana.net`, base path
`/otlp`, numeric instance ID and non-placeholder token. Placeholders, unsafe env
syntax and other endpoints are rejected. If Grafana changes its official endpoint
shape, review this contract rather than bypassing validation.

## 7. Explicitly activate export and verify Alloy

Activation forwards the existing host/self metrics, allowlisted platform journal
logs and future local OTLP input, in addition to the synthetic smoke telemetry.
Local retention continues. Run:

```sh
sudo python3 /usr/local/lib/blaine/grafana-cloud.py activate
systemctl is-active alloy
curl --fail --silent --show-error http://127.0.0.1:12345/-/healthy
sudo test -f /etc/blaine/infra/cloud.enabled
```

Expected: activation succeeds, Alloy is `active`, HTTP health succeeds and the
marker test exits 0. The helper combines the local config and inactive cloud
fragment, validates the candidate, installs it and restarts Alloy. systemd reads
`/etc/blaine/secrets/grafana-cloud.env` using its optional `EnvironmentFile`; Alloy
reads the three fields through `sys.env()` and exports OTLP HTTP with basic auth
and bounded retry/queue settings. No fake values enter an active exporter.

The marker preserves explicit activation across Ansible applies. A reload alone
cannot reread systemd's EnvironmentFile: repeat activation/restart after credential
materialization. Alloy health alone does not prove successful remote delivery.

## 8. Emit one synthetic metric, log and trace

From the repository directory established in step 1:

```sh
date -u +%FT%TZ
python3 infra/smoke-otlp.py
```

Expected: `traces: accepted locally`, `metrics: accepted locally`,
`logs: accepted locally`, and a synthetic trace ID. The script only sends to
`127.0.0.1:4318`; it invokes no model or real application workload. Record the
printed ID and UTC time, neither of which is a credential. Allow the five-second
batch flush and a short backend indexing interval before querying. Local
acceptance is not evidence of cloud arrival.

## 9. Verify all three signals in Grafana Cloud

Open **Explore** in the **same stack**, set **Last 15 minutes**, and choose each
provisioned data source by type: **Tempo** for traces, **Loki** for logs,
**Prometheus** for metrics. Names vary by stack. These logged-in UI queries require
no additional read token.

For Tempo, select **Trace ID**, paste the ID printed by the smoke script and run
the query. Confirm service `blaine-d1-synthetic`, span `d1-activation-smoke` and the
recent timestamp. Alternatively search with TraceQL:

```traceql
{ resource.service.name = "blaine-d1-synthetic" }
```

For Loki, run this LogQL and confirm the emitted message and recent timestamp:

```logql
{service_name="blaine-d1-synthetic"} |= "D1 synthetic activation smoke"
```

For Prometheus, run this PromQL; the expected value is **1**. The name expression
accepts normalized underscores or OTLP dots, while the range retains the single
emitted gauge sample:

```promql
max_over_time({__name__=~"d1[._]synthetic[._]value",job="blaine-d1-synthetic"}[15m])
```

The [Grafana OTLP mappings](https://grafana.com/docs/grafana-cloud/observe-and-act/send-data/otlp/otlp-format-considerations/)
explain service/name conversion. If stack-specific mappings differ, use Explore's
label/metric browser to locate the emitted service/name and record the mapping.
One smoke span need not populate an Application Observability dashboard; direct
Explore results are the acceptance evidence.

Optional local exporter-counter check, without credentials or raw logs:

```sh
curl --fail --silent --show-error http://127.0.0.1:12345/metrics |
  rg '^otelcol_exporter_(sent|send_failed|enqueue_failed)_(spans|metric_points|log_records)(_total)?[{ ].*grafana_cloud'
```

Sent counters should increase after emission. Persistent failures require
investigation. Counter success alone does not prove all three signals queryable.
Record UTC time, stack URL, trace ID, the successful log query and metric value
in an operator acceptance note without credentials. Only after all three are
visible mark runtime delivery **CONNECTED / VERIFIED**. D1 preparation is already
complete; this future acceptance remains unperformed.

## 10. Recover, rotate credentials and finish securely

If nothing appears, first check stack, data source and time range. For HTTP 401/403,
check instance ID, token expiry and all three stack-scoped write permissions.
For endpoint/DNS/TLS failures, recopy the connection details; do not disable TLS
verification. For a single missing signal, check its scope and query mapping.
Do not repeatedly emit synthetic data to mask an exporter failure.

Disable remote export while preserving local telemetry:

```sh
sudo python3 /usr/local/lib/blaine/grafana-cloud.py deactivate
systemctl is-active alloy
curl --fail --silent --show-error http://127.0.0.1:12345/-/healthy
sudo test ! -e /etc/blaine/infra/cloud.enabled
```

Expected: local Alloy healthy, activation marker absent. Deactivation does not
erase the runtime credential or Bitwarden item. Correct/rotate values in Bitwarden,
unlock and sync, repeat materialization, lock/unset the session, then activate
and repeat the smoke and three delivery checks. Never paste raw configuration,
environment files or logs into a diagnostic report.

At the end of either successful activation or troubleshooting:

```sh
bw lock
unset BW_SESSION
sudo -k
```

D1's `/etc/sudoers.d/90-blaine-d1-codex` rule was removed and revocation verified.
These future commands use normal operator-authenticated sudo; do not recreate that
rule. Observability failure never becomes a Task/runtime dependency or authority.

Additional official references checked on 2026-09-20:

- [Grafana OTLP ingestion](https://grafana.com/docs/opentelemetry/ingest/)
- [Alloy OTLP configuration](https://grafana.com/docs/opentelemetry/collector/grafana-alloy/)
