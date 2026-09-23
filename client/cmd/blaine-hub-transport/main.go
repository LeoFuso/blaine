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
	"blaine.local/client/internal/workstation"
	"tailscale.com/client/local"
)

type config struct {
	Listen         string `json:"listen"`
	KeyFile        string `json:"key_file"`
	Python         string `json:"python"`
	Repository     string `json:"repository"`
	ReadinessFile  string `json:"readiness_file"`
	DeploymentFile string `json:"deployment_file"`
	RegistryDSN    string `json:"registry_dsn"`
	Admission      string `json:"admission"`
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
	if cfg.RegistryDSN == "" || cfg.Admission != "tailscale-policy" {
		return fmt.Errorf("explicit registry and Tailscale admission required")
	}
	if len(flag.Args()) > 0 {
		return inventory(cfg.RegistryDSN, flag.Args(), os.Stdout)
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
	bounded, done := context.WithTimeout(ctx, 5*time.Second)
	registry, e := workstation.Open(bounded, cfg.RegistryDSN, true)
	done()
	if e != nil {
		return e
	}
	defer registry.Close()
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
		return direct.AdmittedPeer(who)
	}
	host.Register = func(ctx context.Context, peer direct.Peer, hello direct.Hello, session string) (string, error) {
		if hello.Platform == "" {
			hello.Platform = peer.Metadata.Platform
		}
		if hello.Architecture == "" {
			hello.Architecture = peer.Metadata.Architecture
		}
		if hello.DisplayName == "" {
			hello.DisplayName = peer.Metadata.DisplayName
		}
		record, created, err := registry.Connect(ctx, workstation.Binding{Tailnet: bootstrap.Tailnet, NodeID: peer.NodeID, PrincipalID: peer.PrincipalID, InstallationID: hello.ClientID}, workstation.Metadata{DisplayName: hello.DisplayName, Platform: hello.Platform, Architecture: hello.Architecture, ClientVersion: hello.Version}, session)
		if err != nil {
			return "", err
		}
		stage := "reconnected"
		if created {
			stage = "created"
		}
		diagnosticMu.Lock()
		defer diagnosticMu.Unlock()
		_ = json.NewEncoder(os.Stderr).Encode(map[string]any{"event": "workstation", "stage": stage, "workstation_id": record.ID, "peer_node": peer.NodeID, "session_id": session, "protocol": hello.Max, "outcome": "OK"})
		return record.ID, nil
	}
	host.Touch = registry.Touch
	host.Disconnect = func(ctx context.Context, session string) error {
		err := registry.Disconnect(ctx, session)
		outcome := "OK"
		if err != nil {
			outcome = "REGISTRY_UNAVAILABLE"
		}
		diagnosticMu.Lock()
		defer diagnosticMu.Unlock()
		_ = json.NewEncoder(os.Stderr).Encode(map[string]any{"event": "workstation", "stage": "disconnected", "session_id": session, "outcome": outcome})
		return err
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
		return direct.RelayHost(parent, s, process.Spec{Executable: cfg.Python, Args: []string{"-m", "runtime.personal_acp"}, Env: []string{"PYTHONPATH=" + cfg.Repository, "PYTHONDONTWRITEBYTECODE=1", "BLAINE_D2_INGRESS=http://127.0.0.1:48080", "BLAINE_WORKSTATION_ID=" + s.WorkstationID}}, os.Stderr)
	}
	listener, e := net.Listen("tcp", cfg.Listen)
	if e != nil {
		return e
	}
	server := &http.Server{Handler: host, ReadHeaderTimeout: 5 * time.Second, MaxHeaderBytes: 8192, BaseContext: func(net.Listener) context.Context { return ctx }}
	stopped := context.AfterFunc(ctx, func() { server.Close() })
	defer stopped()
	_ = json.NewEncoder(os.Stderr).Encode(map[string]any{"event": "private_listener_ready", "protocol": direct.Protocol, "server_id": bootstrap.ServerID})
	e = server.Serve(listener)
	if ctx.Err() != nil {
		return nil
	}
	return e
}

// Host-local operator reads; no tsnet enrollment, presence refresh or write.
func inventory(dsn string, args []string, out io.Writer) error {
	if len(args) < 2 || args[0] != "workstation" || !((len(args) == 2 && args[1] == "list") || (len(args) == 3 && args[1] == "inspect")) {
		return fmt.Errorf("usage: --config FILE workstation list|inspect ID")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	store, err := workstation.Open(ctx, dsn, false)
	if err != nil {
		return err
	}
	defer store.Close()
	if args[1] == "list" {
		rows, e := store.List(ctx)
		if e != nil {
			return e
		}
		return json.NewEncoder(out).Encode(rows)
	}
	row, e := store.Inspect(ctx, args[2])
	if e != nil {
		return e
	}
	return json.NewEncoder(out).Encode(row)
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
