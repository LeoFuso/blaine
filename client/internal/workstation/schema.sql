-- E0.D inventory only. No Task ledger or capability grants.
CREATE SCHEMA blaine_workstations;
CREATE TABLE blaine_workstations.schema_version (version integer PRIMARY KEY CHECK (version = 1));
INSERT INTO blaine_workstations.schema_version VALUES (1);
CREATE TABLE blaine_workstations.workstation (
    workstation_id text PRIMARY KEY CHECK (workstation_id ~ '^ws-[0-9a-f]{32}$'),
    tailnet text NOT NULL,
    transport_node_id text NOT NULL,
    principal_id text NOT NULL,
    installation_id text NOT NULL,
    display_name text NOT NULL,
    platform text NOT NULL,
    architecture text NOT NULL,
    client_version text NOT NULL,
    first_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (tailnet, transport_node_id)
);
CREATE TABLE blaine_workstations.connection (
    session_id text PRIMARY KEY,
    workstation_id text NOT NULL REFERENCES blaine_workstations.workstation,
    instance_id text NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE INDEX ON blaine_workstations.connection (workstation_id);
