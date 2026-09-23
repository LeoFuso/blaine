package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"tailscale.com/ipn/ipnstate"
	"tailscale.com/types/key"
)

func testStatus(visible bool) *ipnstate.Status {
	s := &ipnstate.Status{BackendState: "Running", Self: &ipnstate.PeerStatus{ID: "client-node"},
		CurrentTailnet: &ipnstate.TailnetStatus{MagicDNSSuffix: "tail0f2ece.ts.net"}}
	if visible {
		s.Peer = map[key.NodePublic]*ipnstate.PeerStatus{{}: {ID: "nYBs8Z3gD511CNTRL", DNSName: "blaine.tail0f2ece.ts.net."}}
	}
	return s
}

func TestWaitForExpectedHub(t *testing.T) {
	t.Run("Running alone is insufficient", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Millisecond)
		defer cancel()
		if _, err := waitForHub(ctx, func(context.Context) (*ipnstate.Status, error) { return testStatus(false), nil }, "client-node"); err == nil {
			t.Fatal("missing Hub accepted")
		}
	})
	t.Run("delayed map succeeds without restarting", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		calls := 0
		_, err := waitForHub(ctx, func(context.Context) (*ipnstate.Status, error) {
			calls++
			return testStatus(calls > 1), nil
		}, "client-node")
		if err != nil || calls != 2 {
			t.Fatal("delayed peer not observed", err, calls)
		}
	})
	t.Run("cancellation prevents status call", func(t *testing.T) {
		ctx, cancel := context.WithCancel(context.Background())
		cancel()
		_, err := waitForHub(ctx, func(context.Context) (*ipnstate.Status, error) {
			t.Fatal("status called after cancellation")
			return nil, nil
		}, "client-node")
		if err == nil {
			t.Fatal("cancellation ignored")
		}
	})
	for _, condition := range []string{"wrong tailnet", "changed node", "wrong Hub name"} {
		t.Run(condition, func(t *testing.T) {
			s := testStatus(true)
			switch condition {
			case "wrong tailnet":
				s.CurrentTailnet.MagicDNSSuffix = "unexpected.example"
			case "changed node":
				s.Self.ID = "other-node"
			case "wrong Hub name":
				s.Peer[key.NodePublic{}].DNSName = "unexpected.example"
			}
			if _, err := waitForHub(context.Background(), func(context.Context) (*ipnstate.Status, error) { return s, nil }, "client-node"); err == nil {
				t.Fatal("identity mismatch accepted")
			}
		})
	}
}

func TestObservationBaselineDoesNotRequireStream(t *testing.T) {
	dir := t.TempDir()
	if reused, err := recordNodeObservation(dir, "node-a"); err != nil || reused {
		t.Fatal("first observation", reused, err)
	}
	if reused, err := recordNodeObservation(dir, "node-a"); err != nil || !reused {
		t.Fatal("repeat observation", reused, err)
	}
	if _, err := recordNodeObservation(dir, "node-b"); err == nil {
		t.Fatal("changed identity silently accepted")
	}
	p := filepath.Join(dir, "observed-node-id")
	b, err := os.ReadFile(p)
	if err != nil || string(b) != "node-a" {
		t.Fatal("baseline overwritten", err)
	}
	info, err := os.Stat(p)
	if err != nil || info.Mode().Perm() != 0600 {
		t.Fatal("baseline permissions", err)
	}
}
