package main

import (
	"context"
	"encoding/json"
	"errors"
	"net"
	"strings"
	"syscall"
	"time"

	"tailscale.com/client/local"
	"tailscale.com/tsnet"
)

// Never emit raw backend errors/logs: they may include authentication material.
func dialFailure(err error) map[string]any {
	r := map[string]any{"kind": "other"}
	var dns *net.DNSError
	var op *net.OpError
	switch {
	case errors.As(err, &dns):
		r["kind"] = "dns"
		r["not_found"] = dns.IsNotFound
		r["timeout"] = dns.IsTimeout
		r["temporary"] = dns.IsTemporary
	case errors.Is(err, context.DeadlineExceeded):
		r["kind"] = "deadline"
	case errors.Is(err, context.Canceled):
		r["kind"] = "cancelled"
	case errors.Is(err, syscall.ECONNREFUSED):
		r["kind"] = "connection_refused"
	case errors.Is(err, syscall.ENETUNREACH):
		r["kind"] = "network_unreachable"
	case errors.Is(err, syscall.EHOSTUNREACH):
		r["kind"] = "host_unreachable"
	case errors.As(err, &op):
		r["kind"] = "network_operation"
		r["timeout"] = op.Timeout()
	}
	return r
}

func embeddedSnapshot(parent context.Context, lc *local.Client) map[string]any {
	r := map[string]any{}
	ctx, cancel := context.WithTimeout(parent, 5*time.Second)
	st, err := lc.Status(ctx)
	cancel()
	if err == nil {
		r["embedded_backend_state"] = st.BackendState
		r["embedded_health_warning_count"] = len(st.Health)
		visible := false
		for _, p := range st.Peer {
			if string(p.ID) == "nYBs8Z3gD511CNTRL" {
				visible = true
				r["hub_name_matches"] = strings.TrimSuffix(p.DNSName, ".") == "blaine.tail0f2ece.ts.net"
			}
		}
		r["hub_in_embedded_peer_map"] = visible
	} else {
		r["embedded_status_error"] = dialFailure(err)
	}
	return r
}

// Measurement only: one process, no login/Dial retries and no state mutation.
// Keep changes plus the final sample, rather than emitting private netmaps.
func observePeerMap(parent context.Context, lc *local.Client, duration time.Duration) map[string]any {
	ctx, cancel := context.WithTimeout(parent, duration)
	defer cancel()
	started := time.Now()
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	changes := []map[string]any{}
	var last map[string]any
	previous := ""
	samples := 0
	for {
		snapshot := embeddedSnapshot(ctx, lc)
		if ctx.Err() != nil {
			break
		}
		samples++
		encoded, _ := json.Marshal(snapshot)
		last = map[string]any{"elapsed_ms": time.Since(started).Milliseconds(), "snapshot": snapshot}
		if string(encoded) != previous {
			changes = append(changes, last)
			previous = string(encoded)
		}
		select {
		case <-ctx.Done():
			return map[string]any{"sample_count": samples, "changes": changes, "last_sample": last, "window_ms": time.Since(started).Milliseconds()}
		case <-ticker.C:
		}
	}
	return map[string]any{"sample_count": samples, "changes": changes, "last_sample": last, "window_ms": time.Since(started).Milliseconds()}
}

func diagnoseConnectivity(parent context.Context, s *tsnet.Server, lc *local.Client) map[string]any {
	r := embeddedSnapshot(parent, lc)
	r["status"] = "DIAGNOSTIC_ONLY"
	r["scope"] = "no stream or production acceptance"
	// The observed canonical IP is a diagnostic control, never a fallback that
	// turns a failed hostname into PASS. Both require the same trusted node ID.
	for _, target := range []struct{ label, address string }{
		{"magicdns", destination},
		{"observed_hub_ipv4", "100.94.139.5:49173"},
	} {
		ctx, cancel := context.WithTimeout(parent, 12*time.Second)
		start := time.Now()
		conn, err := s.Dial(ctx, "tcp", target.address)
		entry := map[string]any{"elapsed_ms": time.Since(start).Milliseconds()}
		if err != nil {
			entry["tcp"] = "FAIL"
			entry["error"] = dialFailure(err)
		} else {
			entry["tcp"] = "PASS"
			who, err := lc.WhoIs(ctx, conn.RemoteAddr().String())
			conn.Close()
			entry["hub_identity_verified"] = err == nil && who.Node != nil &&
				string(who.Node.StableID) == "nYBs8Z3gD511CNTRL" &&
				strings.TrimSuffix(who.Node.Name, ".") == "blaine.tail0f2ece.ts.net"
		}
		cancel()
		r[target.label] = entry
	}
	return r
}
