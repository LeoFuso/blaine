package direct

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"github.com/coder/websocket"
	"tailscale.com/client/local"
	"tailscale.com/tsnet"
)

// Network uses its own userspace stack. No machine-wide CLI, socket, daemon,
// TUN device, incoming listener, routes, SSH server or reusable auth key.
type Network struct {
	Installation *Installation
	Server       *tsnet.Server
	Local        *local.Client
	Node         string
	Reused       bool
	Bootstrap    Bootstrap
}

func OpenNetwork(ctx context.Context, root string, b Bootstrap, interactive bool, diagnostics io.Writer) (*Network, error) {
	for _, name := range []string{"TS_AUTHKEY", "TS_CLIENT_ID", "TS_CLIENT_SECRET", "TS_ID_TOKEN", "TSNET_FORCE_LOGIN", "TS_ID_TOKEN_FILE", "TS_AUDIENCE", "TS_LOGIN_SERVER", "TS_CONTROL_URL"} {
		if os.Getenv(name) != "" {
			return nil, fmt.Errorf("LOCAL_INVALID: unset %s; embedded client requires interactive enrollment", name)
		}
	}
	if !interactive {
		if _, e := os.Lstat(filepath.Join(root, "direct-v1", "node-id")); e != nil {
			return nil, errors.New("AUTH_REQUIRED: authenticate through ACP or run blaine connect")
		}
	}
	i, e := OpenInstallation(root)
	if e != nil {
		return nil, e
	}
	n := &Network{Installation: i, Bootstrap: b}
	success := false
	defer func() {
		if !success {
			n.Close()
		}
	}()
	ready, cancel := context.WithTimeout(ctx, 3*time.Minute)
	defer cancel()
	var once sync.Once
	var authErr error
	var authMu sync.Mutex
	userLog := func(format string, args ...any) {
		for _, part := range strings.Fields(fmt.Sprintf(format, args...)) {
			u, e := url.Parse(part)
			if e != nil || u.Scheme != "https" || u.Host != "login.tailscale.com" || u.User != nil {
				continue
			}
			once.Do(func() {
				authMu.Lock()
				defer authMu.Unlock()
				if !interactive {
					authErr = errors.New("AUTH_REQUIRED: authenticate through ACP or run blaine connect")
					cancel()
					return
				}
				fmt.Fprintln(diagnostics, "Blaine private network authentication required; opening browser. Do not share the authentication URL.")
				if openBrowser(ctx, part) != nil {
					authErr = errors.New("BROWSER_UNAVAILABLE: browser launch failed; no authentication URL written to logs")
					cancel()
				}
			})
		}
	}
	n.Server = &tsnet.Server{Dir: filepath.Join(i.Dir, "tsnet"), Hostname: "blaine-" + strings.TrimPrefix(i.ID(), "ws-")[:12], UserLogf: userLog, Logf: func(string, ...any) {}}
	if e = n.Server.Start(); e != nil {
		return nil, errors.New("NETWORK_START_FAILED: embedded network")
	}
	n.Local, e = n.Server.LocalClient()
	if e != nil {
		return nil, errors.New("NETWORK_START_FAILED: embedded control")
	}
	// Login waits are bounded and noninteractive re-auth returns AUTH_REQUIRED.
	st, e := n.Server.Up(ready)
	authMu.Lock()
	aerr := authErr
	authMu.Unlock()
	if aerr != nil {
		return nil, aerr
	}
	if e != nil {
		return nil, errors.New("NETWORK_UNAVAILABLE: embedded login/start deadline or cancellation")
	}
	if st.Self == nil || st.CurrentTailnet == nil || st.CurrentTailnet.MagicDNSSuffix != b.Tailnet {
		return nil, errors.New("IDENTITY_MISMATCH: unexpected tailnet")
	}
	n.Node = string(st.Self.ID)
	n.Reused, e = i.ObserveNode(n.Node)
	if e != nil {
		return nil, e
	}
	if e = n.checkProfile(); e != nil {
		return nil, e
	}
	wait, stop := context.WithTimeout(ctx, 20*time.Second)
	defer stop()
	if e = n.waitForHub(wait); e != nil {
		return nil, e
	}
	success = true
	return n, nil
}
func (n *Network) waitForHub(ctx context.Context) error {
	host, _, e := net.SplitHostPort(n.Bootstrap.Endpoint)
	if e != nil {
		return errors.New("BOOTSTRAP_INVALID")
	}
	ticker := time.NewTicker(200 * time.Millisecond)
	defer ticker.Stop()
	for {
		st, e := n.Local.Status(ctx)
		if e != nil {
			return errors.New("NETWORK_UNAVAILABLE: embedded status")
		}
		if st.Self == nil || string(st.Self.ID) != n.Node || st.CurrentTailnet == nil || st.CurrentTailnet.MagicDNSSuffix != n.Bootstrap.Tailnet {
			return errors.New("IDENTITY_MISMATCH: embedded identity changed")
		}
		for _, peer := range st.Peer {
			if string(peer.ID) == n.Bootstrap.HubNode {
				if strings.TrimSuffix(peer.DNSName, ".") != host {
					return errors.New("IDENTITY_MISMATCH: Hub name")
				}
				return nil
			}
		}
		select {
		case <-ctx.Done():
			return errors.New("HUB_NOT_VISIBLE: expected peer absent before deadline")
		case <-ticker.C:
		}
	}
}
func (n *Network) dial(ctx context.Context, network, address string) (net.Conn, error) {
	if network != "tcp" || address != n.Bootstrap.Endpoint {
		return nil, errors.New("TRANSPORT_DENIED: unexpected destination")
	}
	c, e := n.Server.Dial(ctx, "tcp", address)
	if e != nil {
		return nil, errors.New("HUB_UNREACHABLE: private TCP path")
	}
	who, e := n.Local.WhoIs(ctx, c.RemoteAddr().String())
	if e != nil || who == nil || who.Node == nil || who.Node.Expired || string(who.Node.StableID) != n.Bootstrap.HubNode {
		c.Close()
		return nil, errors.New("IDENTITY_MISMATCH: destination node")
	}
	return c, nil
}
func (n *Network) Connect(ctx context.Context, mode string) (*Session, Challenge, error) {
	transport := &http.Transport{DialContext: n.dial, DisableKeepAlives: true}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("TRANSPORT_DENIED: redirect") }}
	bounded, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	c, httpResponse, e := websocket.Dial(bounded, "ws://"+n.Bootstrap.Endpoint+"/v1/session", &websocket.DialOptions{HTTPClient: client, Subprotocols: []string{Subprotocol}, CompressionMode: websocket.CompressionDisabled})
	if e != nil {
		if httpResponse != nil && httpResponse.StatusCode == 403 {
			return nil, Challenge{}, errors.New("TRANSPORT_DENIED: authenticated node is not authorized by Hub deployment policy")
		}
		return nil, Challenge{}, errors.New("HUB_UNREACHABLE: private application endpoint")
	}
	if c.Subprotocol() != Subprotocol {
		c.CloseNow()
		return nil, Challenge{}, errors.New("INCOMPATIBLE: transport subprotocol")
	}
	session, response, e := ClientHandshake(ctx, c, n.Installation.Key, n.Bootstrap, n.Node, mode)
	if e != nil {
		c.CloseNow()
	}
	if e == nil {
		e = n.saveProfile()
		if e != nil {
			session.Close()
			session = nil
			e = errors.New("STATE_INVALID: cannot persist verified profile")
		}
	}
	return session, response, e
}
func (n *Network) Close() error {
	var e error
	if n.Server != nil {
		e = n.Server.Close()
	}
	if n.Installation != nil {
		n.Installation.Close()
	}
	return e
}
func openBrowser(ctx context.Context, raw string) error {
	bounded, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	name, args := "xdg-open", []string{raw}
	kernel, _ := os.ReadFile("/proc/sys/kernel/osrelease")
	if runtime.GOOS == "darwin" {
		name = "/usr/bin/open"
	} else if strings.Contains(strings.ToLower(string(kernel)), "microsoft") {
		// WSL invokes the Windows browser only, not Windows Tailscale. A single quoted
		// PowerShell literal contains a validated provider URL; it is never shell text.
		name = "powershell.exe"
		args = []string{"-NoProfile", "-NonInteractive", "-Command", "Start-Process -FilePath '" + strings.ReplaceAll(raw, "'", "''") + "'"}
	}
	cmd := exec.CommandContext(bounded, name, args...)
	cmd.Stdout = io.Discard
	cmd.Stderr = io.Discard
	return cmd.Run()
}
