package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"tailscale.com/ipn/ipnstate"
)

// The caller holds the installation lock. This file is measurement metadata,
// not node credentials or Blaine registration, and is independent of stream PASS.
func recordNodeObservation(dir, node string) (bool, error) {
	if node == "" {
		return false, errors.New("embedded node identity missing")
	}
	path := filepath.Join(dir, "observed-node-id")
	previous, err := os.ReadFile(path)
	if err == nil {
		if string(previous) != node {
			return false, errors.New("node identity changed across launches; review state")
		}
		return true, nil
	}
	if !errors.Is(err, os.ErrNotExist) {
		return false, errors.New("cannot read node observation baseline")
	}
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return false, errors.New("cannot create node observation baseline")
	}
	_, err = f.WriteString(node)
	closeErr := f.Close()
	return false, errors.Join(err, closeErr)
}

// Wait for this expected peer, not a generic Online flag or fixed startup delay.
// There are no login or connection retries. Dial and WhoIs remain required.
func waitForHub(ctx context.Context, status func(context.Context) (*ipnstate.Status, error), node string) (int64, error) {
	started := time.Now()
	ticker := time.NewTicker(200 * time.Millisecond)
	defer ticker.Stop()
	for {
		if ctx.Err() != nil {
			return time.Since(started).Milliseconds(), fmt.Errorf("expected Hub peer unavailable before deadline/cancellation: %w", ctx.Err())
		}
		st, err := status(ctx)
		if err != nil {
			return time.Since(started).Milliseconds(), errors.New("embedded status unavailable while waiting for Hub")
		}
		if st == nil || st.Self == nil || string(st.Self.ID) != node || st.CurrentTailnet == nil || st.CurrentTailnet.MagicDNSSuffix != "tail0f2ece.ts.net" {
			return time.Since(started).Milliseconds(), errors.New("embedded identity or tailnet changed while waiting for Hub")
		}
		for _, p := range st.Peer {
			if string(p.ID) != "nYBs8Z3gD511CNTRL" {
				continue
			}
			if strings.TrimSuffix(p.DNSName, ".") != "blaine.tail0f2ece.ts.net" {
				return time.Since(started).Milliseconds(), errors.New("expected Hub name/identity mismatch")
			}
			if st.BackendState == "Running" {
				return time.Since(started).Milliseconds(), nil
			}
		}
		select {
		case <-ctx.Done():
		case <-ticker.C:
		}
	}
}
