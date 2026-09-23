// Package direct implements the bounded private E0.C transport. It grants no
// workspace authority and owns no durable Task lifecycle.
package direct

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	_ "embed"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"runtime"
	"strings"
	"time"

	"blaine.local/client/internal/buildinfo"
	"blaine.local/client/internal/wire"
	"github.com/coder/websocket"
)

const Subprotocol = "blaine.e0c.v1"
const Protocol = 2
const Data byte = 1
const End byte = 2
const Cancel byte = 3
const Exit byte = 4
const MaxFrame = wire.Limit + 17

//go:embed bootstrap.json
var deployment []byte

type Bootstrap struct {
	Schema    int    `json:"schema"`
	Endpoint  string `json:"endpoint"`
	Tailnet   string `json:"tailnet"`
	HubNode   string `json:"hub_node_id"`
	ServerID  string `json:"server_id"`
	ServerKey string `json:"server_public_key"`
}

func Deployment() Bootstrap {
	var b Bootstrap
	if wire.Decode(deployment, &b) != nil {
		panic("invalid embedded deployment")
	}
	return b
}
func RandomID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b)
}
func keyID(prefix string, key []byte) string {
	h := sha256.Sum256(key)
	return prefix + hex.EncodeToString(h[:16])
}
func Public(key ed25519.PrivateKey) string {
	return base64.StdEncoding.EncodeToString(key.Public().(ed25519.PublicKey))
}
func decodeKey(s string) (ed25519.PublicKey, error) {
	b, e := base64.StdEncoding.DecodeString(s)
	if e != nil || len(b) != ed25519.PublicKeySize {
		return nil, errors.New("IDENTITY_INVALID: public key")
	}
	return b, nil
}

type Hello struct {
	Schema       int    `json:"schema"`
	Min          int    `json:"min_protocol"`
	Max          int    `json:"max_protocol"`
	Version      string `json:"client_version"`
	ServerID     string `json:"expected_server_id"`
	ClientID     string `json:"client_id"`
	PublicKey    string `json:"client_public_key"`
	Nonce        string `json:"nonce"`
	Mode         string `json:"mode"`
	Platform     string `json:"platform,omitempty"`
	Architecture string `json:"architecture,omitempty"`
	DisplayName  string `json:"display_name,omitempty"`
}
type Peer struct {
	NodeID      string `json:"node_id"`
	PrincipalID string `json:"principal_id"`
	// Host-only descriptive LocalAPI observation; not part of transport identity
	// or the legacy signed wire shape. Client claims cannot populate this field.
	Metadata PeerMetadata `json:"-"`
}
type PeerMetadata struct{ DisplayName, Platform, Architecture string }
type Challenge struct {
	Schema       int               `json:"schema"`
	Protocol     int               `json:"protocol"`
	ServerID     string            `json:"server_id"`
	Version      string            `json:"server_version"`
	PublicKey    string            `json:"server_public_key"`
	SessionID    string            `json:"session_id"`
	Nonce        string            `json:"nonce"`
	Peer         Peer              `json:"peer"`
	Readiness    map[string]string `json:"readiness"`
	Registration string            `json:"registration"`
	Signature    string            `json:"signature"`
}
type Proof struct {
	Signature string `json:"signature"`
}
type Ready struct {
	SessionID     string `json:"session_id"`
	Status        string `json:"status"`
	WorkstationID string `json:"workstation_id,omitempty"`
	Signature     string `json:"signature,omitempty"`
}

func receiptTranscript(h Hello, c Challenge, r Ready) []byte {
	r.Signature = ""
	b, _ := json.Marshal(r)
	return append(append([]byte("blaine-registration-v2\x00"), transcript(h, c)...), b...)
}
func validateReady(h Hello, c Challenge, r Ready, b Bootstrap) error {
	if r.SessionID != c.SessionID || r.Status != "CONNECTED" {
		return errors.New("HANDSHAKE_INVALID: acknowledgement")
	}
	if c.Protocol == 2 {
		key, e := decodeKey(b.ServerKey)
		if e != nil || !validWorkstationID(r.WorkstationID) || !verify(key, receiptTranscript(h, c, r), r.Signature) {
			return errors.New("REGISTRATION_INVALID: signed receipt")
		}
	}
	return nil
}
func validWorkstationID(id string) bool {
	return strings.HasPrefix(id, "ws-") && validID(strings.TrimPrefix(id, "ws-"))
}

func transcript(h Hello, c Challenge) []byte {
	c.Signature = ""
	b, _ := json.Marshal(struct {
		Domain    string
		Hello     Hello
		Challenge Challenge
	}{"blaine-e0c-auth-v1", h, c})
	return b
}
func proofTranscript(h Hello, c Challenge) []byte {
	return append([]byte("blaine-client-proof-v1\x00"), transcript(h, c)...)
}
func sign(k ed25519.PrivateKey, b []byte) string {
	return base64.StdEncoding.EncodeToString(ed25519.Sign(k, b))
}
func verify(k ed25519.PublicKey, b []byte, s string) bool {
	sig, e := base64.StdEncoding.DecodeString(s)
	return e == nil && ed25519.Verify(k, b, sig)
}
func readControl(ctx context.Context, c *websocket.Conn, v any) error {
	typ, b, e := c.Read(ctx)
	if e != nil {
		return e
	}
	if typ != websocket.MessageText || len(b) > 65536 {
		return errors.New("PROTOCOL_INVALID: control frame")
	}
	return wire.Decode(b, v)
}
func writeControl(ctx context.Context, c *websocket.Conn, v any) error {
	b, e := json.Marshal(v)
	if e != nil {
		return e
	}
	return c.Write(ctx, websocket.MessageText, b)
}
func HelloFor(k ed25519.PrivateKey, b Bootstrap, mode string) Hello {
	return Hello{Schema: 1, Min: 2, Max: 2, Version: buildinfo.Current().ClientVersion, ServerID: b.ServerID, ClientID: keyID("ws-", k.Public().(ed25519.PublicKey)), PublicKey: Public(k), Nonce: RandomID(), Mode: mode, Platform: runtime.GOOS, Architecture: runtime.GOARCH}
}
func validID(s string) bool { b, e := hex.DecodeString(s); return e == nil && len(b) == 16 }
func validateHello(h Hello, b Bootstrap) error {
	key, e := decodeKey(h.PublicKey)
	if e != nil || h.Schema != 1 || !validID(h.Nonce) || h.ClientID != keyID("ws-", key) || h.ServerID != b.ServerID || len(h.Version) == 0 || len(h.Version) > 128 {
		return errors.New("IDENTITY_INVALID: hello")
	}
	if h.Min > 2 || h.Max < 1 || h.Min < 1 || h.Max < h.Min {
		return errors.New("INCOMPATIBLE: protocol")
	}
	if h.Mode != "acp" && h.Mode != "probe" && h.Mode != "handshake" {
		return errors.New("PROTOCOL_INVALID: mode")
	}
	for _, s := range []string{h.Platform, h.Architecture, h.DisplayName} {
		if len(s) > 128 || strings.ContainsAny(s, "\x00\r\n\t") {
			return errors.New("PROTOCOL_INVALID: metadata")
		}
	}
	if h.Max >= 2 && (h.Platform == "" || h.Architecture == "") {
		return errors.New("PROTOCOL_INVALID: metadata required")
	}
	return nil
}
func ValidateChallenge(h Hello, c Challenge, b Bootstrap, node string) error {
	key, e := decodeKey(b.ServerKey)
	registrationOK := (c.Protocol == 1 && c.Registration == "not-implemented") || (c.Protocol == 2 && c.Registration == "automatic")
	if e != nil || c.Schema != 1 || c.Protocol < h.Min || c.Protocol > h.Max || !registrationOK || c.Version == "" || len(c.Version) > 128 || c.ServerID != b.ServerID || c.PublicKey != b.ServerKey || !validID(c.Nonce) || !validID(c.SessionID) || c.Peer.NodeID != node || c.Peer.PrincipalID == "" || !verify(key, transcript(h, c), c.Signature) {
		return errors.New("IDENTITY_MISMATCH: signed Hub handshake rejected")
	}
	for _, name := range []string{"runtime", "restate", "mirix", "generation", "embeddings"} {
		if c.Readiness[name] != "PASS" {
			return fmt.Errorf("DEPENDENCY_UNAVAILABLE: %s=%s", name, c.Readiness[name])
		}
	}
	return nil
}

type Session struct {
	Conn          *websocket.Conn
	ID            string
	ctx           context.Context
	WorkstationID string
}

func NewSession(ctx context.Context, c *websocket.Conn, id string) *Session {
	c.SetReadLimit(MaxFrame)
	return &Session{Conn: c, ID: id, ctx: ctx}
}
func (s *Session) Send(ctx context.Context, kind byte, b []byte) error {
	id, e := hex.DecodeString(s.ID)
	if e != nil || len(id) != 16 || len(b) > wire.Limit || kind < Data || kind > Exit {
		return errors.New("PROTOCOL_INVALID: frame")
	}
	frame := make([]byte, 17+len(b))
	frame[0] = kind
	copy(frame[1:17], id)
	copy(frame[17:], b)
	return s.Conn.Write(ctx, websocket.MessageBinary, frame)
}
func (s *Session) Receive(ctx context.Context) (byte, []byte, error) {
	typ, b, e := s.Conn.Read(ctx)
	if e != nil {
		return 0, nil, e
	}
	id, _ := hex.DecodeString(s.ID)
	if typ != websocket.MessageBinary || len(b) < 17 || len(b) > MaxFrame || !bytes.Equal(b[1:17], id) || b[0] < Data || b[0] > Exit {
		return 0, nil, errors.New("PROTOCOL_INVALID: session/frame")
	}
	return b[0], b[17:], nil
}
func (s *Session) Close() { s.Conn.CloseNow() }
func ClientHandshake(ctx context.Context, c *websocket.Conn, k ed25519.PrivateKey, b Bootstrap, node, mode string) (*Session, Challenge, error) {
	bounded, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	c.SetReadLimit(65536)
	h := HelloFor(k, b, mode)
	var response Challenge
	if e := writeControl(bounded, c, h); e != nil {
		return nil, response, e
	}
	if e := readControl(bounded, c, &response); e != nil {
		return nil, response, errors.New("HANDSHAKE_INVALID: response")
	}
	if e := ValidateChallenge(h, response, b, node); e != nil {
		return nil, response, e
	}
	if e := writeControl(bounded, c, Proof{sign(k, proofTranscript(h, response))}); e != nil {
		return nil, response, e
	}
	var ready Ready
	if e := readControl(bounded, c, &ready); e != nil {
		return nil, response, errors.New("HANDSHAKE_INVALID: acknowledgement")
	}
	if e := validateReady(h, response, ready, b); e != nil {
		return nil, response, e
	}
	s := NewSession(ctx, c, response.SessionID)
	s.WorkstationID = ready.WorkstationID
	return s, response, nil
}
