package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"os"
	"strings"
	"testing"

	"blaine.local/client/internal/workstation"
	"github.com/jackc/pgx/v5"
)

func TestOperatorInventoryIsReadOnlyAndSanitized(t *testing.T) {
	dsn := os.Getenv("BLAINE_TEST_POSTGRES_DSN")
	if dsn == "" {
		t.Skip("use private PostgreSQL fixture runner")
	}
	ctx := context.Background()
	c, e := pgx.Connect(ctx, dsn)
	if e != nil {
		t.Fatal(e)
	}
	defer c.Close(ctx)
	var directory string
	if c.QueryRow(ctx, "SHOW data_directory").Scan(&directory) != nil || !strings.Contains(directory, "blaine-registry-test-") {
		t.Fatal("not a private fixture")
	}
	if _, e = c.Exec(ctx, "DROP SCHEMA IF EXISTS blaine_workstations CASCADE;"+workstation.Schema); e != nil {
		t.Fatal(e)
	}
	store, e := workstation.Open(ctx, dsn, true)
	if e != nil {
		t.Fatal(e)
	}
	defer store.Close()
	r, _, e := store.Connect(ctx, workstation.Binding{Tailnet: "fixture", NodeID: "node", PrincipalID: "owner", InstallationID: "ws-11111111111111111111111111111111"}, workstation.Metadata{DisplayName: "Laptop", Platform: "darwin", Architecture: "arm64", ClientVersion: "fixture"}, "session")
	if e != nil {
		t.Fatal(e)
	}
	var out bytes.Buffer
	if e = inventory(dsn, []string{"workstation", "list"}, &out); e != nil {
		t.Fatal(e)
	}
	var rows []workstation.Record
	// JSON UTC decoding and pgx may use different Location pointers for the
	// same instant. Inventory reads must preserve the instant, not that pointer.
	if json.Unmarshal(out.Bytes(), &rows) != nil || len(rows) != 1 || rows[0].ID != r.ID || rows[0].Presence != "ONLINE" || !rows[0].LastSeen.Equal(r.LastSeen) {
		t.Fatal(out.String())
	}
	for _, secret := range []string{"password", "private_key", "auth_key", dsn} {
		if strings.Contains(out.String(), secret) {
			t.Fatal("private inventory material")
		}
	}
	out.Reset()
	if e = inventory(dsn, []string{"workstation", "inspect", r.ID}, &out); e != nil {
		t.Fatal(e)
	}
	var row workstation.Record
	if json.Unmarshal(out.Bytes(), &row) != nil || row.ID != r.ID || !row.LastSeen.Equal(r.LastSeen) {
		t.Fatal(out.String())
	}
	out.Reset()
	if e = inventory(dsn, []string{"workstation", "inspect", "ws-00000000000000000000000000000000"}, &out); !errors.Is(e, workstation.ErrNotFound) || out.Len() != 0 {
		t.Fatal(e, out.String())
	}
	if e = inventory(dsn, []string{"workstation", "approve", r.ID}, &out); e == nil {
		t.Fatal("manual approval exposed")
	}
}
