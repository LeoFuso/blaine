package direct

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"
)

func TestRegistrationOnlyAfterClientProofAndStorageFailureCloses(t *testing.T) {
	h, url, key := testHost(t)
	var calls atomic.Int32
	h.Register = func(context.Context, Peer, Hello, string) (string, error) {
		calls.Add(1)
		return "", errors.New("fixture storage unavailable")
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	c := dialTest(t, url)
	hello := HelloFor(key, h.Bootstrap, "acp")
	if e := writeControl(ctx, c, hello); e != nil {
		t.Fatal(e)
	}
	var challenge Challenge
	if e := readControl(ctx, c, &challenge); e != nil {
		t.Fatal(e)
	}
	if calls.Load() != 0 {
		t.Fatal("registered before key proof")
	}
	if e := writeControl(ctx, c, Proof{Signature: "bad"}); e != nil {
		t.Fatal(e)
	}
	var ack Ready
	if readControl(ctx, c, &ack) == nil {
		t.Fatal("bad proof got receipt")
	}
	if calls.Load() != 0 {
		t.Fatal("bad proof registered")
	}
	if _, _, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "acp"); e == nil {
		t.Fatal("missing storage accepted")
	}
	if calls.Load() != 1 {
		t.Fatal(calls.Load())
	}
}
func TestLegacyV1WireRemainsCompatibleWithoutClaimingClientReceipt(t *testing.T) {
	h, url, key := testHost(t)
	var registered atomic.Bool
	h.Register = func(context.Context, Peer, Hello, string) (string, error) {
		registered.Store(true)
		return "ws-0123456789abcdef0123456789abcdef", nil
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	hello := HelloFor(key, h.Bootstrap, "handshake")
	hello.Min = 1
	hello.Max = 1
	hello.Platform = ""
	hello.Architecture = ""
	c := dialTest(t, url)
	if e := writeControl(ctx, c, hello); e != nil {
		t.Fatal(e)
	}
	var challenge Challenge
	if e := readControl(ctx, c, &challenge); e != nil {
		t.Fatal(e)
	}
	if challenge.Protocol != 1 || challenge.Registration != "not-implemented" {
		t.Fatal("legacy wire contract changed", challenge)
	}
	if e := ValidateChallenge(hello, challenge, h.Bootstrap, "fixture-node"); e != nil {
		t.Fatal(e)
	}
	if e := writeControl(ctx, c, Proof{sign(key, proofTranscript(hello, challenge))}); e != nil {
		t.Fatal(e)
	}
	var raw map[string]any
	if e := readControl(ctx, c, &raw); e != nil {
		t.Fatal(e)
	}
	if !registered.Load() || len(raw) != 2 || raw["status"] != "CONNECTED" {
		t.Fatal(raw, registered.Load())
	}
}
func TestRegistrationReceiptPinsAndProtocolUpgrade(t *testing.T) {
	i, e := OpenInstallation(t.TempDir())
	if e != nil {
		t.Fatal(e)
	}
	defer i.Close()
	b, _, _ := keys(t)
	n := &Network{Installation: i, Bootstrap: b, Node: "node"}
	legacy := n.expectedProfile()
	legacy.Protocol = 1
	raw, _ := json.Marshal(legacy)
	if e = os.WriteFile(filepath.Join(i.Dir, "connection.json"), raw, 0600); e != nil {
		t.Fatal(e)
	}
	if e = n.checkProfile(); e != nil {
		t.Fatal("unchanged legacy pins rejected", e)
	}
	if e = n.saveProfile(); e != nil {
		t.Fatal(e)
	}
	if e = n.checkProfile(); e != nil {
		t.Fatal(e)
	}
	a := "ws-11111111111111111111111111111111"
	if e = n.saveRegistration(a); e != nil {
		t.Fatal(e)
	}
	if e = n.saveRegistration(a); e != nil {
		t.Fatal(e)
	}
	if e = n.saveRegistration("ws-22222222222222222222222222222222"); e == nil {
		t.Fatal("registry reassignment accepted")
	}
	n.Node = "another"
	if e = n.saveRegistration(a); e == nil {
		t.Fatal("node transfer accepted")
	}
}

func TestSignedReceiptCannotSubstituteWorkstationOrSession(t *testing.T) {
	b, server, client := keys(t)
	h := HelloFor(client, b, "acp")
	c := Challenge{Protocol: 2, SessionID: RandomID(), Peer: Peer{NodeID: "node", PrincipalID: "owner"}}
	r := Ready{SessionID: c.SessionID, Status: "CONNECTED", WorkstationID: "ws-11111111111111111111111111111111"}
	r.Signature = sign(server, receiptTranscript(h, c, r))
	if e := validateReady(h, c, r, b); e != nil {
		t.Fatal(e)
	}
	for _, mutate := range []func(*Ready){func(r *Ready) { r.WorkstationID = "ws-22222222222222222222222222222222" }, func(r *Ready) { r.SessionID = RandomID() }, func(r *Ready) { r.Signature = "" }} {
		changed := r
		mutate(&changed)
		if validateReady(h, c, changed, b) == nil {
			t.Fatal("substituted receipt accepted")
		}
	}
	h.Nonce = RandomID()
	if validateReady(h, c, r, b) == nil {
		t.Fatal("receipt replay accepted")
	}
}
