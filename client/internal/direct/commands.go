package direct

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"tailscale.com/tsnet"
)

func Connect(ctx context.Context, root string, interactive, verifyTransport bool, out, diagnostics io.Writer) error {
	n, e := OpenNetwork(ctx, root, Deployment(), interactive, diagnostics)
	if e != nil {
		return e
	}
	defer n.Close()
	// Public identity observation helps the operator deploy the narrow host policy;
	// it is neither credentials nor an E0.D registration receipt.
	_ = json.NewEncoder(out).Encode(map[string]any{"installation_id": n.Installation.ID(), "node_id": n.Node, "node_reused": n.Reused, "embedded_mtu": n.MTU.Value, "mtu_source": n.MTU.Source})
	s, response, e := n.Connect(ctx, "handshake")
	if e != nil {
		return e
	}
	defer s.Close()
	kind, b, e := s.Receive(ctx)
	if e != nil || kind != Exit || len(b) != 1 || b[0] != 0 {
		return errors.New("HANDSHAKE_INVALID: session completion")
	}
	if verifyTransport {
		report, e := VerifyTransport(ctx, n)
		_ = json.NewEncoder(out).Encode(report)
		if e != nil {
			return e
		}
	}
	return json.NewEncoder(out).Encode(map[string]any{"status": "CONNECTED", "server_id": response.ServerID, "session_id": response.SessionID, "workstation_id": s.WorkstationID, "peer": response.Peer, "registration": "REGISTERED", "e0": "NOT_READY"})
}

// Logout uses the embedded control API, never system Tailscale. Identity reset is
// allowed only after logout succeeds; no silent deletion or automatic re-pairing.
func Logout(parent context.Context, root string, reset bool) error {
	dir := filepath.Join(root, "direct-v1")
	if _, e := os.Lstat(dir); errors.Is(e, os.ErrNotExist) {
		return nil
	}
	i, e := OpenInstallation(root)
	if e != nil {
		return e
	}
	defer i.Close()
	if _, e = prepareNetworkMTU(); e != nil {
		return e
	}
	server := &tsnet.Server{Dir: filepath.Join(i.Dir, "tsnet"), Hostname: "blaine-" + strings.TrimPrefix(i.ID(), "ws-")[:12], UserLogf: func(string, ...any) {}, Logf: func(string, ...any) {}}
	if e = server.Start(); e != nil {
		return errors.New("LOGOUT_UNAVAILABLE: state preserved")
	}
	lc, e := server.LocalClient()
	if e != nil {
		server.Close()
		return errors.New("LOGOUT_UNAVAILABLE: embedded control")
	}
	ctx, cancel := context.WithTimeout(parent, 10*time.Second)
	defer cancel()
	e = lc.Logout(ctx)
	closed := server.Close()
	if e != nil || closed != nil {
		return errors.New("LOGOUT_UNCONFIRMED: state preserved; inspect tailnet administration")
	}
	if reset {
		// Keep the lease inode in place until the operation completes. A new process
		// must acquire it before generating either application or network identity.
		entries, e := os.ReadDir(i.Dir)
		if e != nil {
			return e
		}
		for _, entry := range entries {
			if entry.Name() != "installation.lock" {
				if e = os.RemoveAll(filepath.Join(i.Dir, entry.Name())); e != nil {
					return e
				}
			}
		}
	}
	return nil
}
func ExitCode(err error) int {
	if err == nil {
		return 0
	}
	if errors.Is(err, context.Canceled) {
		return 130
	}
	if strings.HasPrefix(err.Error(), "INCOMPATIBLE") {
		return 4
	}
	for _, prefix := range []string{"STATE_", "LOCAL_", "AUTH_REQUIRED", "INSTANCE_BUSY", "IDENTITY_CHANGED", "BROWSER_"} {
		if strings.HasPrefix(err.Error(), prefix) {
			return 2
		}
	}
	return 3
}
