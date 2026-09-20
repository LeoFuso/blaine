# Grafana Cloud activation runbook

State: **CONFIGURED FOR FUTURE ACTIVATION**. No account/stack exists for this D1
pass, no remote exporter is active, and no delivery to Grafana Cloud is claimed.
Local Alloy remains healthy without cloud values or an unlocked vault.

1. Create a Grafana Cloud account and stack. Open the stack's OpenTelemetry
   connection/setup page (the Cloud Portal also exposes the OTLP connection
   details). Copy the current OTLP HTTP **base endpoint**, including `/otlp`.
   Do not substitute the Grafana UI URL or append `/v1/traces` to the base value.
2. Copy the **OTLP instance ID / username from those same connection details**.
   Do not guess it from an email, organization ID or unrelated metrics instance.
3. Create a **Cloud Access Policy token**, scoped to this stack's realm, with
   `metrics:write`, `logs:write`, and `traces:write`. Use the connection UI's
   token-generation flow or the stack's Cloud access policies screen. Set a useful
   expiry and record rotation ownership. A Grafana service-account token for the
   dashboard HTTP API is a different credential and does not grant OTLP ingestion.
4. Authenticate/unlock Bitwarden locally using its official CLI or client. Never
   paste the master password or token into this conversation. For the CLI:

   ```sh
   bw login
   export BW_SESSION="$(bw unlock --raw)"
   python3 /usr/local/lib/blaine/grafana-cloud.py status
   python3 /usr/local/lib/blaine/grafana-cloud.py placeholder
   ```

   `BW_SESSION` exists only in the operator's shell environment; never write it to
   a profile, file, Git or systemd. If already logged in, omit `bw login`.
   The helper creates a secure note only if the named item is absent and the vault
   is unlocked; it never enumerates/dumps the vault or replaces an existing item.
   The exact item name is **Blaine / Grafana Cloud**, with these fields:

   | Field | Placeholder / final value |
   |---|---|
   | `GRAFANA_CLOUD_OTLP_ENDPOINT` | `REPLACE_ME_NOT_ACTIVE` → actual HTTPS Grafana OTLP base endpoint |
   | `GRAFANA_CLOUD_OTLP_USERNAME` | `REPLACE_ME_NOT_ACTIVE` → numeric OTLP instance identifier |
   | `GRAFANA_CLOUD_OTLP_API_KEY` | `REPLACE_ME_NOT_ACTIVE` → scoped access-policy token (hidden field) |

   Replace the placeholders in the Bitwarden UI, then `bw sync` if needed.
5. Materialize only the three selected fields:

   ```sh
   sudo -v
   python3 /usr/local/lib/blaine/grafana-cloud.py materialize
   unset BW_SESSION
   bw lock
   ```

   The helper captures the selected item privately, rejects placeholders, unsafe
   environment syntax and non-Grafana endpoints, and passes only validated fields
   over stdin to its bounded root writer. Destination:
   `/etc/blaine/secrets/grafana-cloud.env`, root-owned **0600**, root parent **0700**.
   The file is outside Git. No background synchronization or runtime vault access
   exists. Do not `cat`/`source` the file or include it in diagnostic bundles.
   This step does **not** enable export.
6. Explicitly enable the prepared exporter:

   ```sh
   sudo python3 /usr/local/lib/blaine/grafana-cloud.py activate
   ```

   The helper composes the local pipeline and inactive cloud fragment, validates
   the candidate, then installs it and restarts Alloy. systemd reads the optional
   `EnvironmentFile`; Alloy accesses only the three `sys.env()` values. The same
   local telemetry branches to OTLP HTTP with basic authentication and bounded
   retry/queue settings. A missing or placeholder secret cannot activate it.
   `/etc/blaine/infra/cloud.enabled` records explicit activation so Ansible does
   not replace cloud configuration with the local-only baseline.
7. Check `systemctl is-active alloy` and
   `curl --fail http://127.0.0.1:12345/-/healthy`. A reload alone cannot reread
   systemd's EnvironmentFile; restart after materializing changed credentials.
8. Emit synthetic telemetry without invoking a model or an application workload:

   ```sh
   python3 infra/smoke-otlp.py
   ```

   This emits one metric, log and trace to **127.0.0.1:4318** and prints only the
   synthetic trace ID. Local acceptance does not prove remote delivery.
9. In Grafana Explore / Application Observability, find service
   `blaine-d1-synthetic` and the printed trace ID. In the logs data source, find
   `D1 synthetic activation smoke`; in metrics, find `d1_synthetic_value` (the
   backend may normalize OTLP metric punctuation). Check current timestamps and
   successful exporter counters. Record evidence for all three signals before
   changing the state from configured to connected.
10. If delivery fails, preserve local operation and disable the exporter while
    diagnosing endpoint/token scopes privately:

    ```sh
    sudo python3 /usr/local/lib/blaine/grafana-cloud.py deactivate
    ```

    Deactivation restores the local pipeline and removes the activation marker;
    it does not erase the runtime credential or Bitwarden item. Token rotation is
    an explicit repeat of materialization and activation, not a background daemon.

This D1 session's temporary sudoers rule must be removed at finalization. The
future commands above use normal operator-authenticated sudo; the rule is not a
runtime prerequisite. Observability outages never acquire Task/runtime authority.

Official references checked on 2026-09-20:

- [Grafana OTLP ingestion](https://grafana.com/docs/opentelemetry/ingest/)
- [Alloy OTLP configuration](https://grafana.com/docs/opentelemetry/collector/grafana-alloy/)
- [Cloud Access Policies, realms and tokens](https://grafana.com/docs/grafana-cloud/platform/security-and-account-management/security-and-access/authentication-and-permissions/access-policies/)
- [Write scopes for the three signals](https://grafana.com/docs/grafana-cloud/observe-and-act/agent-observability/get-started/grafana-cloud/)
- [Official Bitwarden CLI](https://bitwarden.com/help/cli/)
