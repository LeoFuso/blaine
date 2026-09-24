// Package workstation owns PostgreSQL inventory, not admission or Task lifecycle.
package workstation

import (
	"context"
	"crypto/rand"
	_ "embed"
	"encoding/hex"
	"errors"
	"regexp"
	"strings"
	"sync"
	"time"
	"unicode"

	"github.com/jackc/pgx/v5"
)

//go:embed schema.sql
var Schema string

var ErrUnavailable = errors.New("REGISTRY_UNAVAILABLE: storage or schema unavailable")
var ErrInvalid = errors.New("REGISTRY_INVALID: invalid identity or metadata")
var ErrNotFound = errors.New("WORKSTATION_NOT_FOUND")
var idPattern = regexp.MustCompile(`^ws-[0-9a-f]{32}$`)

const Lease = 45 * time.Second
const ownerLock int64 = 0x424c41494e454430

// Binding is supplied only after socket identity and client key proof validation.
// IP, hostname and client-chosen workstation IDs are deliberately absent.
type Binding struct {
	Tailnet, NodeID, PrincipalID, InstallationID string
}
type Metadata struct {
	DisplayName   string `json:"display_name"`
	Platform      string `json:"platform"`
	Architecture  string `json:"architecture"`
	ClientVersion string `json:"client_version"`
}
type Record struct {
	ID             string `json:"workstation_id"`
	Tailnet        string `json:"tailnet"`
	NodeID         string `json:"transport_node_id"`
	PrincipalID    string `json:"principal_id"`
	InstallationID string `json:"installation_id"`
	Metadata
	FirstSeen time.Time `json:"first_seen_at"`
	LastSeen  time.Time `json:"last_seen_at"`
	Presence  string    `json:"presence"`
}
type Store struct {
	mu       sync.Mutex
	conn     *pgx.Conn
	instance string
}

func randomID() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b[:])
}
func bounded(s string, required bool) bool {
	return (!required || s != "") && len(s) <= 128 && !strings.ContainsFunc(s, unicode.IsControl)
}
func validate(b Binding, m Metadata) bool {
	return bounded(b.Tailnet, true) && bounded(b.NodeID, true) && bounded(b.PrincipalID, true) && idPattern.MatchString(b.InstallationID) && bounded(m.DisplayName, false) && bounded(m.Platform, false) && bounded(m.Architecture, false) && bounded(m.ClientVersion, true)
}

// Open never creates/migrates schema. A writer holds a DB session advisory lock;
// a second edge cannot clear its live routes. Crash recovery clears old routes.
// Inventory readers need no lock and never refresh presence.
func Open(ctx context.Context, dsn string, writer bool) (*Store, error) {
	c, e := pgx.Connect(ctx, dsn)
	if e != nil {
		return nil, ErrUnavailable
	}
	s := &Store{conn: c}
	fail := func() (*Store, error) { c.Close(context.Background()); return nil, ErrUnavailable }
	var version int
	if c.QueryRow(ctx, "SELECT version FROM blaine_workstations.schema_version").Scan(&version) != nil || version != 1 {
		return fail()
	}
	rows, e := c.Query(ctx, selectRecord+" LIMIT 0")
	if e != nil {
		return fail()
	}
	rows.Close()
	if writer {
		var owned bool
		if c.QueryRow(ctx, "SELECT pg_try_advisory_lock($1)", ownerLock).Scan(&owned) != nil || !owned {
			return fail()
		}
		s.instance = randomID()
		if _, e = c.Exec(ctx, "DELETE FROM blaine_workstations.connection"); e != nil {
			return fail()
		}
	}
	return s, nil
}
func (s *Store) Close() {
	s.mu.Lock()
	defer s.mu.Unlock()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if s.instance != "" {
		_, _ = s.conn.Exec(ctx, "DELETE FROM blaine_workstations.connection WHERE instance_id=$1", s.instance)
	}
	_ = s.conn.Close(ctx)
}

const columns = `w.workstation_id,w.tailnet,w.transport_node_id,w.principal_id,w.installation_id,w.display_name,w.platform,w.architecture,w.client_version,w.first_seen_at,w.last_seen_at`
const selectRecord = `SELECT ` + columns + `, CASE WHEN EXISTS (SELECT 1 FROM blaine_workstations.connection c WHERE c.workstation_id=w.workstation_id AND c.expires_at>clock_timestamp()) THEN 'ONLINE' ELSE 'OFFLINE' END FROM blaine_workstations.workstation w`

func scan(row pgx.Row) (Record, error) {
	var r Record
	e := row.Scan(&r.ID, &r.Tailnet, &r.NodeID, &r.PrincipalID, &r.InstallationID, &r.DisplayName, &r.Platform, &r.Architecture, &r.ClientVersion, &r.FirstSeen, &r.LastSeen, &r.Presence)
	if errors.Is(e, pgx.ErrNoRows) {
		return r, ErrNotFound
	}
	if e != nil || !idPattern.MatchString(r.ID) || !validate(Binding{r.Tailnet, r.NodeID, r.PrincipalID, r.InstallationID}, r.Metadata) || r.FirstSeen.After(r.LastSeen) {
		return Record{}, ErrUnavailable
	}
	return r, nil
}

// Connect transactionally upserts by authenticated node, never by metadata or
// installation key. A distinct admitted node gets a distinct server-assigned ID.
func (s *Store) Connect(ctx context.Context, b Binding, m Metadata, session string) (Record, bool, error) {
	if !validate(b, m) || !bounded(session, true) {
		return Record{}, false, ErrInvalid
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.instance == "" {
		return Record{}, false, ErrUnavailable
	}
	tx, e := s.conn.Begin(ctx)
	if e != nil {
		return Record{}, false, ErrUnavailable
	}
	defer tx.Rollback(context.Background())
	candidate := "ws-" + randomID()
	tag, e := tx.Exec(ctx, `INSERT INTO blaine_workstations.workstation (workstation_id,tailnet,transport_node_id,principal_id,installation_id,display_name,platform,architecture,client_version) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (tailnet,transport_node_id) DO NOTHING`, candidate, b.Tailnet, b.NodeID, b.PrincipalID, b.InstallationID, m.DisplayName, m.Platform, m.Architecture, m.ClientVersion)
	if e != nil {
		return Record{}, false, ErrUnavailable
	}
	created := tag.RowsAffected() == 1
	var id string
	e = tx.QueryRow(ctx, `UPDATE blaine_workstations.workstation SET principal_id=$3,installation_id=$4,display_name=$5,platform=$6,architecture=$7,client_version=$8,last_seen_at=clock_timestamp() WHERE tailnet=$1 AND transport_node_id=$2 RETURNING workstation_id`, b.Tailnet, b.NodeID, b.PrincipalID, b.InstallationID, m.DisplayName, m.Platform, m.Architecture, m.ClientVersion).Scan(&id)
	if e != nil {
		return Record{}, false, ErrUnavailable
	}
	tag, e = tx.Exec(ctx, `INSERT INTO blaine_workstations.connection VALUES ($1,$2,$3,clock_timestamp()+ interval '45 seconds') ON CONFLICT (session_id) DO UPDATE SET expires_at=EXCLUDED.expires_at WHERE blaine_workstations.connection.workstation_id=EXCLUDED.workstation_id AND blaine_workstations.connection.instance_id=EXCLUDED.instance_id`, session, id, s.instance)
	if e != nil || tag.RowsAffected() != 1 {
		return Record{}, false, ErrUnavailable
	}
	r, e := scan(tx.QueryRow(ctx, selectRecord+" WHERE w.workstation_id=$1", id))
	if e != nil {
		return Record{}, false, e
	}
	if tx.Commit(ctx) != nil {
		return Record{}, false, ErrUnavailable
	}
	return r, created, nil
}
func (s *Store) Touch(ctx context.Context, session string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.instance == "" {
		return ErrUnavailable
	}
	tag, e := s.conn.Exec(ctx, `WITH touched AS (UPDATE blaine_workstations.connection SET expires_at=clock_timestamp()+ interval '45 seconds' WHERE session_id=$1 AND instance_id=$2 RETURNING workstation_id) UPDATE blaine_workstations.workstation SET last_seen_at=clock_timestamp() WHERE workstation_id IN (SELECT workstation_id FROM touched)`, session, s.instance)
	if e != nil || tag.RowsAffected() != 1 {
		return ErrUnavailable
	}
	return nil
}
func (s *Store) Disconnect(ctx context.Context, session string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.instance == "" {
		return ErrUnavailable
	}
	_, e := s.conn.Exec(ctx, `WITH removed AS (DELETE FROM blaine_workstations.connection WHERE session_id=$1 AND instance_id=$2 RETURNING workstation_id) UPDATE blaine_workstations.workstation SET last_seen_at=clock_timestamp() WHERE workstation_id IN (SELECT workstation_id FROM removed)`, session, s.instance)
	if e != nil {
		return ErrUnavailable
	}
	return nil
}
func (s *Store) List(ctx context.Context) ([]Record, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	rows, e := s.conn.Query(ctx, selectRecord+" ORDER BY w.first_seen_at,w.workstation_id LIMIT 1001")
	if e != nil {
		return nil, ErrUnavailable
	}
	defer rows.Close()
	out := []Record{}
	for rows.Next() {
		r, e := scan(rows)
		if e != nil {
			return nil, e
		}
		out = append(out, r)
	}
	if rows.Err() != nil || len(out) > 1000 {
		return nil, ErrUnavailable
	}
	return out, nil
}
func (s *Store) Inspect(ctx context.Context, id string) (Record, error) {
	if !idPattern.MatchString(id) {
		return Record{}, ErrInvalid
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return scan(s.conn.QueryRow(ctx, selectRecord+" WHERE w.workstation_id=$1", id))
}
