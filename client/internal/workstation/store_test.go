package workstation

import (
	"context"
	"errors"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
)

func fixture(t *testing.T) (context.Context, string, *pgx.Conn) {
	t.Helper()
	dsn := os.Getenv("BLAINE_TEST_POSTGRES_DSN")
	if dsn == "" {
		t.Skip("use tests/with_postgres.py for isolated PostgreSQL acceptance")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	t.Cleanup(cancel)
	c, e := pgx.Connect(ctx, dsn)
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { c.Close(context.Background()) })
	// Only the explicit disposable fixture environment may execute destructive DDL.
	var user string
	if c.QueryRow(ctx, "SELECT current_user").Scan(&user) != nil || user != "fixture" {
		t.Fatal("not a disposable registry fixture")
	}
	var directory string
	if c.QueryRow(ctx, "SHOW data_directory").Scan(&directory) != nil || !strings.Contains(directory, "blaine-registry-test-") {
		t.Fatal("not a private fixture cluster")
	}
	if _, e = c.Exec(ctx, "DROP SCHEMA IF EXISTS blaine_workstations CASCADE;"+Schema); e != nil {
		t.Fatal(e)
	}
	return ctx, dsn, c
}
func binding(node string) Binding {
	return Binding{"fixture.tailnet", node, "fixture-principal", "ws-11111111111111111111111111111111"}
}
func metadata() Metadata { return Metadata{"Same laptop name", "darwin", "arm64", "fixture-v1"} }
func TestDurableIdentityPresenceAndRestart(t *testing.T) {
	ctx, dsn, _ := fixture(t)
	s, e := Open(ctx, dsn, true)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	r, created, e := s.Connect(ctx, binding("node-A"), metadata(), "session-1")
	if e != nil || !created || r.Presence != "ONLINE" {
		t.Fatal(r, created, e)
	}
	id := r.ID
	if id == binding("node-A").InstallationID {
		t.Fatal("client installation nominated registry ID")
	}
	// Idempotent retry after a lost receipt, then new ACP conversation.
	for _, session := range []string{"session-1", "session-2"} {
		r, created, e = s.Connect(ctx, binding("node-A"), metadata(), session)
		if e != nil || created || r.ID != id {
			t.Fatal(r, created, e)
		}
	}
	if e = s.Disconnect(ctx, "session-1"); e != nil {
		t.Fatal(e)
	}
	r, e = s.Inspect(ctx, id)
	if e != nil || r.Presence != "ONLINE" {
		t.Fatal("old session closed newer presence", r, e)
	}
	firstSeen, lastSeen := r.FirstSeen, r.LastSeen
	if e = s.Touch(ctx, "session-2"); e != nil {
		t.Fatal(e)
	}
	r, _ = s.Inspect(ctx, id)
	if !r.LastSeen.After(lastSeen) {
		t.Fatal("observation did not advance")
	}
	if e = s.Disconnect(ctx, "session-2"); e != nil {
		t.Fatal(e)
	}
	r, e = s.Inspect(ctx, id)
	if e != nil || r.Presence != "OFFLINE" {
		t.Fatal(r, e)
	}
	m := metadata()
	m.DisplayName = "Renamed laptop"
	m.ClientVersion = "fixture-upgrade"
	r, created, e = s.Connect(ctx, binding("node-A"), m, "session-3")
	if e != nil || created || r.ID != id || r.FirstSeen != firstSeen {
		t.Fatal(r, created, e)
	}
	if _, e = Open(ctx, dsn, true); e == nil {
		t.Fatal("second edge cleared live routes")
	}
	// Abrupt DB connection loss models an edge crash, not graceful Disconnect.
	s.conn.Close(ctx)
	again, e := Open(ctx, dsn, true)
	if e != nil {
		t.Fatal(e)
	}
	defer again.Close()
	r, e = again.Inspect(ctx, id)
	if e != nil || r.Presence != "OFFLINE" {
		t.Fatal("restart left stale route", r, e)
	}
	r, created, e = again.Connect(ctx, binding("node-A"), m, "session-4")
	if e != nil || created || r.ID != id {
		t.Fatal(r, created, e)
	}
	rows, e := again.List(ctx)
	if e != nil || len(rows) != 1 {
		t.Fatal(rows, e)
	}
	// Same metadata and same client key/claimed installation on a distinct node
	// cannot inherit the first row. Transport identity alone selects the binding.
	other, created, e := again.Connect(ctx, binding("node-B"), m, "session-5")
	if e != nil || !created || other.ID == id {
		t.Fatal(other, created, e)
	}
	// Client key/version changes on the SAME authenticated node keep inventory ID.
	b := binding("node-A")
	b.InstallationID = "ws-22222222222222222222222222222222"
	r, created, e = again.Connect(ctx, b, m, "session-6")
	if e != nil || created || r.ID != id {
		t.Fatal(r, created, e)
	}
}
func TestConcurrencyReadOnlyInventoryAndExpiry(t *testing.T) {
	ctx, dsn, c := fixture(t)
	s, e := Open(ctx, dsn, true)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, _, e := s.Connect(ctx, binding("node"), metadata(), randomID()); e != nil {
				t.Error(e)
			}
		}()
	}
	wg.Wait()
	reader, e := Open(ctx, dsn, false)
	if e != nil {
		t.Fatal(e)
	}
	defer reader.Close()
	rows, e := reader.List(ctx)
	if e != nil || len(rows) != 1 || rows[0].Presence != "ONLINE" {
		t.Fatal(rows, e)
	}
	before := rows[0].LastSeen
	if _, _, e = reader.Connect(ctx, binding("another"), metadata(), "bad"); e == nil {
		t.Fatal("inventory reader wrote")
	}
	_, e = c.Exec(ctx, "UPDATE blaine_workstations.connection SET expires_at=clock_timestamp()-interval '1 second'")
	if e != nil {
		t.Fatal(e)
	}
	rows, e = reader.List(ctx)
	if e != nil || rows[0].Presence != "OFFLINE" || rows[0].LastSeen != before {
		t.Fatal(rows, e)
	}
}
func TestStorageAndMetadataFailuresAreClosed(t *testing.T) {
	ctx, dsn, c := fixture(t)
	s, e := Open(ctx, dsn, true)
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	for _, b := range []Binding{{}, binding("")} {
		if _, _, e = s.Connect(ctx, b, metadata(), "x"); !errors.Is(e, ErrInvalid) {
			t.Fatal(e)
		}
	}
	m := metadata()
	m.DisplayName = "untrusted\nmessage"
	if _, _, e = s.Connect(ctx, binding("node"), m, "x"); !errors.Is(e, ErrInvalid) {
		t.Fatal(e)
	}
	rows, _ := s.List(ctx)
	if len(rows) != 0 {
		t.Fatal("invalid input persisted")
	}
	if _, e = c.Exec(ctx, "ALTER TABLE blaine_workstations.workstation RENAME COLUMN platform TO malformed"); e != nil {
		t.Fatal(e)
	}
	if _, _, e = s.Connect(ctx, binding("node"), metadata(), "x"); !errors.Is(e, ErrUnavailable) {
		t.Fatal(e)
	}
	var count int
	c.QueryRow(ctx, "SELECT count(*) FROM blaine_workstations.workstation").Scan(&count)
	if count != 0 {
		t.Fatal("partial failed registration persisted")
	}
	if _, e = Open(ctx, dsn, false); !errors.Is(e, ErrUnavailable) {
		t.Fatal(e)
	}
	s.conn.Close(ctx)
	if _, e = s.List(ctx); !errors.Is(e, ErrUnavailable) {
		t.Fatal(e)
	}
	if _, e = Open(ctx, "host=/nonexistent-blaine-fixture connect_timeout=1", false); !errors.Is(e, ErrUnavailable) {
		t.Fatal(e)
	}
}
