// Host-only private transport edge. Restate and the deployed runtime remain
// independent services; this process owns only short-lived ACP adapters.
package main

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/netip"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"sync"
	"syscall"
	"time"

	"blaine.local/client/internal/direct"
	"blaine.local/client/internal/process"
	"blaine.local/client/internal/wire"
	"tailscale.com/client/local"
)

type config struct {
	Listen         string   `json:"listen"`
	KeyFile        string   `json:"key_file"`
	Python         string   `json:"python"`
	Repository     string   `json:"repository"`
	ReadinessFile  string   `json:"readiness_file"`
	DeploymentFile string   `json:"deployment_file"`
	Principal      string   `json:"principal_id"`
	Nodes          []string `json:"allowed_nodes"`
}

func main() {
	if e := run(); e != nil {
		fmt.Fprintln(os.Stderr, "blaine-hub: configuration, identity or listener unavailable")
		os.Exit(2)
	}
}
func run() error {
	path := flag.String("config", "", "host-owned deployment configuration")
	flag.Parse()
	raw, e := os.ReadFile(*path)
	if e != nil {
		return e
	}
	var cfg config
	if e = wire.Decode(raw, &cfg); e != nil {
		return e
	}
	address, e := netip.ParseAddrPort(cfg.Listen)
	if e != nil || address.Port() != 7443 || !netip.MustParsePrefix("100.64.0.0/10").Contains(address.Addr()) {
		return fmt.Errorf("private tailnet address required")
	}
	for _, p := range []string{cfg.KeyFile, cfg.Python, cfg.Repository, cfg.ReadinessFile, cfg.DeploymentFile} {
		if !filepath.IsAbs(p) {
			return fmt.Errorf("absolute deployment paths required")
		}
	}
	if cfg.Principal == "" || cfg.Nodes == nil {
		return fmt.Errorf("explicit peer node allowlist required")
	}
	info, e := os.Lstat(cfg.KeyFile)
	if e != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
		return fmt.Errorf("private host key required")
	}
	seed, e := os.ReadFile(cfg.KeyFile)
	if e != nil || len(seed) != ed25519.SeedSize {
		return fmt.Errorf("host key invalid")
	}
	key := ed25519.NewKeyFromSeed(seed)
	bootstrap := direct.Deployment()
	if direct.Public(key) != bootstrap.ServerKey {
		return fmt.Errorf("host key does not match deployment bootstrap")
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	lc := &local.Client{}
	status, e := lc.Status(ctx)
	if e != nil || status.Self == nil || string(status.Self.ID) != bootstrap.HubNode || status.CurrentTailnet == nil || status.CurrentTailnet.MagicDNSSuffix != bootstrap.Tailnet {
		return fmt.Errorf("unexpected host node")
	}
	owned := false
	for _, ip := range status.TailscaleIPs {
		if ip == address.Addr() {
			owned = true
		}
	}
	if !owned {
		return fmt.Errorf("listener address not owned")
	}
	host := &direct.Host{Bootstrap: bootstrap, Key: key, Slots: make(chan struct{}, 8)}
	var diagnosticMu sync.Mutex
	host.Observe = func(event direct.Observation) {
		diagnosticMu.Lock()
		defer diagnosticMu.Unlock()
		_ = json.NewEncoder(os.Stderr).Encode(event)
	}
	host.Peer = func(parent context.Context, remote string) (direct.Peer, error) {
		bounded, cancel := context.WithTimeout(parent, 3*time.Second)
		defer cancel()
		who, err := lc.WhoIs(bounded, remote)
		if err != nil {
			return direct.Peer{}, fmt.Errorf("peer unavailable")
		}
		return direct.Authorize(who, cfg.Principal, cfg.Nodes)
	}
	host.Readiness = func(parent context.Context) map[string]string {
		bounded, cancel := context.WithTimeout(parent, 8*time.Second)
		defer cancel()
		cmd := exec.CommandContext(bounded, cfg.Python, "-m", "runtime.direct_readiness", "--config", cfg.ReadinessFile, "--deployment", cfg.DeploymentFile)
		cmd.Dir = cfg.Repository
		cmd.Env = append(os.Environ(), "PYTHONDONTWRITEBYTECODE=1", "PYTHONPATH="+cfg.Repository)
		// Trusted fixed module; stdout is a small readiness map, never memory content.
		var out bytes.Buffer
		cmd.Stdout = &limitedWriter{w: &out, n: 65536}
		cmd.Stderr = io.Discard
		_ = cmd.Run() // A nonzero readiness result still carries per-dependency FAIL/UNKNOWN.
		var result map[string]string
		if wire.Decode(out.Bytes(), &result) != nil {
			return map[string]string{}
		}
		return result
	}
	host.ACP = func(parent context.Context, s *direct.Session) error {
		return direct.RelayHost(parent, s, process.Spec{Executable: cfg.Python, Args: []string{"-m", "runtime.personal_acp"}, Env: []string{"PYTHONPATH=" + cfg.Repository, "PYTHONDONTWRITEBYTECODE=1", "BLAINE_D2_INGRESS=http://127.0.0.1:48080"}}, os.Stderr)
	}
	listener, e := net.Listen("tcp", cfg.Listen)
	if e != nil {
		return e
	}
	server := &http.Server{Handler: host, ReadHeaderTimeout: 5 * time.Second, MaxHeaderBytes: 8192, BaseContext: func(net.Listener) context.Context { return ctx }}
	stopped := context.AfterFunc(ctx, func() { server.Close() })
	defer stopped()
	_ = json.NewEncoder(os.Stderr).Encode(map[string]any{"event": "private_listener_ready", "protocol": 1, "server_id": bootstrap.ServerID})
	e = server.Serve(listener)
	if ctx.Err() != nil {
		return nil
	}
	return e
}

type limitedWriter struct {
	w io.Writer
	n int
}

func (w *limitedWriter) Write(b []byte) (int, error) {
	if len(b) > w.n {
		return 0, fmt.Errorf("readiness limit")
	}
	n, e := w.w.Write(b)
	w.n -= n
	return n, e
}
