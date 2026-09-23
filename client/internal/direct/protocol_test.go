package direct

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"errors"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/coder/websocket"
)

func keys(t *testing.T) (Bootstrap, ed25519.PrivateKey, ed25519.PrivateKey) {
	t.Helper()
	pub, server, e := ed25519.GenerateKey(rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	_, client, e := ed25519.GenerateKey(rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	return Bootstrap{Schema: 1, ServerID: keyID("hub-", pub), ServerKey: Public(server)}, server, client
}
func ready(context.Context) map[string]string {
	return map[string]string{"runtime": "PASS", "restate": "PASS", "mirix": "PASS", "generation": "PASS", "embeddings": "PASS"}
}
func testHost(t *testing.T) (*Host, string, ed25519.PrivateKey) {
	t.Helper()
	b, key, client := keys(t)
	h := &Host{Bootstrap: b, Key: key, Peer: func(context.Context, string) (Peer, error) {
		return Peer{NodeID: "fixture-node", PrincipalID: "fixture-principal"}, nil
	}, Readiness: ready, Slots: make(chan struct{}, 4), Register: func(context.Context, Peer, Hello, string) (string, error) {
		return "ws-0123456789abcdef0123456789abcdef", nil
	}}
	server := httptest.NewServer(h)
	t.Cleanup(server.Close)
	return h, "ws" + strings.TrimPrefix(server.URL, "http") + "/v1/session", client
}
func dialTest(t *testing.T, url string) *websocket.Conn {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	c, _, e := websocket.Dial(ctx, url, &websocket.DialOptions{Subprotocols: []string{Subprotocol}})
	if e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { c.CloseNow() })
	return c
}
func TestHandshakeAndBinaryStream(t *testing.T) {
	h, url, key := testHost(t)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	s, c, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "probe")
	if e != nil {
		t.Fatal(e)
	}
	if c.Peer.NodeID != "fixture-node" || c.Registration != "automatic" {
		t.Fatal(c)
	}
	typ, b, e := s.Receive(ctx)
	if e != nil || typ != Data || !bytes.Equal(b, []byte{0, 1, 13, 10, 127, 128, 255}) {
		t.Fatal(typ, b, e)
	}
	payload := make([]byte, 1<<20)
	for i := range payload {
		payload[i] = byte(i)
	}
	if e = s.Send(ctx, Data, payload); e != nil {
		t.Fatal(e)
	}
	typ, b, e = s.Receive(ctx)
	if e != nil || typ != Data || !bytes.Equal(b, payload) {
		t.Fatal("binary mismatch", e)
	}
	if e = s.Send(ctx, Cancel, nil); e != nil {
		t.Fatal(e)
	}
	typ, b, e = s.Receive(ctx)
	if e != nil || typ != Exit || !bytes.Equal(b, []byte{130}) {
		t.Fatal(typ, b, e)
	}
}
func TestSignedIdentityAndVersionFailClosed(t *testing.T) {
	b, server, client := keys(t)
	h := HelloFor(client, b, "acp")
	c := Challenge{Schema: 1, Protocol: 2, ServerID: b.ServerID, Version: "fixture", PublicKey: b.ServerKey, SessionID: RandomID(), Nonce: RandomID(), Peer: Peer{NodeID: "node", PrincipalID: "user"}, Readiness: ready(context.Background()), Registration: "automatic"}
	c.Signature = sign(server, transcript(h, c))
	if e := ValidateChallenge(h, c, b, "node"); e != nil {
		t.Fatal(e)
	}
	for _, mutate := range []func(*Challenge){func(c *Challenge) { c.ServerID = "wrong" }, func(c *Challenge) { c.Protocol = 3 }, func(c *Challenge) { c.Peer.NodeID = "other" }, func(c *Challenge) { c.SessionID = RandomID() }, func(c *Challenge) { c.Registration = "active" }, func(c *Challenge) { c.Signature = "invalid" }} {
		changed := c
		mutate(&changed)
		if ValidateChallenge(h, changed, b, "node") == nil {
			t.Fatal("accepted changed signed identity")
		}
	}
	replay := h
	replay.Nonce = RandomID()
	if ValidateChallenge(replay, c, b, "node") == nil {
		t.Fatal("replay accepted")
	}
	c.Readiness["mirix"] = "UNKNOWN"
	c.Signature = sign(server, transcript(h, c))
	if ValidateChallenge(h, c, b, "node") == nil {
		t.Fatal("unknown readiness accepted")
	}
	h.Min = 3
	h.Max = 3
	if validateHello(h, b) == nil {
		t.Fatal("protocol mismatch accepted")
	}
}
func TestWrongClientProofAndDeniedPeer(t *testing.T) {
	h, url, key := testHost(t)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	c := dialTest(t, url)
	hello := HelloFor(key, h.Bootstrap, "handshake")
	if e := writeControl(ctx, c, hello); e != nil {
		t.Fatal(e)
	}
	var challenge Challenge
	if e := readControl(ctx, c, &challenge); e != nil {
		t.Fatal(e)
	}
	_ = writeControl(ctx, c, Proof{Signature: sign(h.Key, transcript(hello, challenge))})
	var result Ready
	if readControl(ctx, c, &result) == nil {
		t.Fatal("accepted host key as workstation key")
	}
	h.Peer = func(context.Context, string) (Peer, error) { return Peer{}, errors.New("denied") }
	_, response, e := websocket.Dial(ctx, url, &websocket.DialOptions{Subprotocols: []string{Subprotocol}})
	if e == nil || response.StatusCode != 403 {
		t.Fatal("denied peer upgraded")
	}
}
func TestSessionCorrelationAndDisconnect(t *testing.T) {
	h, url, key := testHost(t)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	s, _, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "probe")
	if e != nil {
		t.Fatal(e)
	}
	_, _, _ = s.Receive(ctx)
	s.ID = RandomID()
	if e = s.Send(ctx, Data, []byte("wrong session")); e != nil {
		t.Fatal(e)
	}
	if _, _, e = s.Receive(ctx); e == nil {
		t.Fatal("wrong session accepted")
	}
}
func TestDependencyFailsOnBothSides(t *testing.T) {
	h, url, key := testHost(t)
	h.Readiness = func(ctx context.Context) map[string]string { m := ready(ctx); m["mirix"] = "UNKNOWN"; return m }
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	_, _, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "handshake")
	if e == nil || !strings.Contains(e.Error(), "DEPENDENCY_UNAVAILABLE") {
		t.Fatal(e)
	}
}

func TestServerSignatureCannotBeReflectedAsClientProof(t *testing.T) {
	h, url, _ := testHost(t)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	c := dialTest(t, url)
	// The attacker nominates the publicly known Hub key as their workstation key.
	hello := HelloFor(h.Key, h.Bootstrap, "handshake")
	if e := writeControl(ctx, c, hello); e != nil {
		t.Fatal(e)
	}
	var response Challenge
	if e := readControl(ctx, c, &response); e != nil {
		t.Fatal(e)
	}
	if e := writeControl(ctx, c, Proof{Signature: response.Signature}); e != nil {
		t.Fatal(e)
	}
	var accepted Ready
	if readControl(ctx, c, &accepted) == nil {
		t.Fatal("reflection accepted")
	}
}
