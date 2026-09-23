// Experimental only: no production Blaine protocol, Task or capability effects.
package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/coder/websocket"
	"tailscale.com/client/local"
	"tailscale.com/tsnet"
)

const destination = "blaine.tail0f2ece.ts.net:49173"

var spikeCommit = "uncommitted"

func emit(v any) { _ = json.NewEncoder(os.Stdout).Encode(v) }
func randomID() string {
	var b [16]byte
	if _, e := rand.Read(b[:]); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b[:])
}
func stateRoot() string {
	p, e := os.UserConfigDir()
	if e != nil {
		panic(e)
	}
	return filepath.Join(p, "BlaineArchitectureSpike")
}
func privateDir(p string) error {
	a, e := filepath.Abs(p)
	if e != nil {
		return e
	}
	for cur := a; ; cur = filepath.Dir(cur) {
		i, e := os.Lstat(cur)
		if e == nil && i.Mode()&os.ModeSymlink != 0 {
			return errors.New("state path contains a symlink")
		}
		if e != nil && !os.IsNotExist(e) {
			return e
		}
		if filepath.Dir(cur) == cur {
			break
		}
	}
	if e = os.MkdirAll(a, 0700); e != nil {
		return e
	}
	i, e := os.Stat(a)
	if e != nil {
		return e
	}
	if i.Mode().Perm()&0077 != 0 {
		return errors.New("state directory must be private (0700)")
	}
	return nil
}
func openBrowser(raw string) error {
	var args []string
	if runtime.GOOS == "darwin" {
		args = []string{"open", raw}
	} else if strings.Contains(strings.ToLower(kernelRelease()), "microsoft") {
		args = []string{"powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Start-Process -FilePath '" + strings.ReplaceAll(raw, "'", "''") + "'"}
	} else {
		args = []string{"xdg-open", raw}
	}
	c := exec.Command(args[0], args[1:]...)
	c.Stdout = io.Discard
	c.Stderr = io.Discard
	return c.Run()
}
func kernelRelease() string { b, _ := os.ReadFile("/proc/sys/kernel/osrelease"); return string(b) }
func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "Modes: acp-mock | tsnet | serve (private fixture only)")
		os.Exit(2)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	var err error
	switch os.Args[1] {
	case "acp-mock":
		err = authAgent(ctx, os.Stdin, os.Stdout, filepath.Join(stateRoot(), "mock-auth"), openBrowser)
	case "tsnet":
		err = tsProbe(ctx)
	case "serve":
		err = serve(ctx)
	default:
		err = errors.New("unknown mode")
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "STOP:", err)
		os.Exit(2)
	}
}

func tsProbe(parent context.Context) error {
	fs := flag.NewFlagSet("tsnet", flag.ContinueOnError)
	diagnose := fs.Bool("diagnose", false, "bounded name/IP diagnostics only; no stream acceptance")
	observePeers := fs.Bool("observe-peers", false, "with --diagnose, observe the same embedded peer map for 20 seconds before dialing")
	if e := fs.Parse(os.Args[2:]); e != nil {
		return e
	}
	if *observePeers && !*diagnose {
		return errors.New("--observe-peers requires --diagnose")
	}
	for _, k := range []string{"TS_AUTHKEY", "TS_CLIENT_ID", "TS_CLIENT_SECRET", "TS_ID_TOKEN", "TSNET_FORCE_LOGIN", "TS_ID_TOKEN_FILE", "TS_AUDIENCE"} {
		if os.Getenv(k) != "" {
			return fmt.Errorf("unset %s; this spike requires explicit interactive login", k)
		}
	}
	dir := filepath.Join(stateRoot(), "tsnet")
	if e := privateDir(dir); e != nil {
		return e
	}
	lock, e := os.OpenFile(filepath.Join(dir, "spike.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if e != nil {
		return e
	}
	defer lock.Close()
	if e = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); e != nil {
		return errors.New("another spike process owns this state; run one at a time")
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	// Separate stable name, never impersonate the machine's existing Tailscale node.
	nameFile := filepath.Join(dir, "node-name")
	b, e := os.ReadFile(nameFile)
	if os.IsNotExist(e) {
		b = []byte("blaine-spike-" + randomID()[:12])
		e = os.WriteFile(nameFile, b, 0600)
	}
	if e != nil {
		return e
	}
	var mu sync.Mutex
	seen := map[string]bool{}
	userlog := func(format string, a ...any) {
		m := fmt.Sprintf(format, a...)
		for _, part := range strings.Fields(m) {
			u, e := url.Parse(part)
			if e != nil || u.Scheme != "https" || u.Host != "login.tailscale.com" {
				continue
			}
			mu.Lock()
			fresh := !seen[part]
			seen[part] = true
			mu.Unlock()
			if fresh {
				fmt.Fprintln(os.Stderr, "Tailscale authentication required; opening your browser. Do not share the URL.")
				if openBrowser(part) != nil {
					fmt.Fprintln(os.Stderr, "Open locally:", part)
				}
			}
		}
	}
	// No Funnel, routes, SSH server, auth keys, tags or listener in the client.
	s := &tsnet.Server{Dir: dir, Hostname: string(b), UserLogf: userlog, Logf: func(string, ...any) {}}
	ctx, cancel := context.WithTimeout(parent, 4*time.Minute)
	defer cancel()
	if e = s.Start(); e != nil {
		return errors.New("tsnet startup failed; no acceptance claimed")
	}
	closed := false
	defer func() {
		if !closed {
			_ = s.Close()
		}
	}()
	st, e := s.Up(ctx)
	if e != nil {
		return errors.New("tsnet login/connectivity did not become ready within deadline")
	}
	if st.CurrentTailnet == nil || st.CurrentTailnet.MagicDNSSuffix != "tail0f2ece.ts.net" {
		return errors.New("unexpected tailnet; no Hub request sent")
	}
	lc, e := s.LocalClient()
	if e != nil {
		return e
	}
	node := string(st.Self.ID)
	reused, e := recordNodeObservation(dir, node)
	if e != nil {
		return e
	}
	if *diagnose {
		var observation map[string]any
		if *observePeers {
			observation = observePeerMap(ctx, lc, 20*time.Second)
		}
		result := diagnoseConnectivity(ctx, s, lc)
		if observation != nil {
			result["peer_observation"] = observation
		}
		result["node_id"] = node
		result["node_reused"] = reused
		result["first_observation"] = !reused
		result["platform"] = runtime.GOOS + "/" + runtime.GOARCH
		result["source_commit"] = spikeCommit
		result["tsnet_version"] = "v1.102.4"
		e = s.Close()
		closed = true
		result["clean_close"] = e == nil
		emit(result)
		return e
	}
	readyCtx, readyCancel := context.WithTimeout(ctx, 20*time.Second)
	readyMS, e := waitForHub(readyCtx, lc.Status, node)
	readyCancel()
	if e != nil {
		return e
	}
	conn, e := s.Dial(ctx, "tcp", destination)
	if e != nil {
		return errors.New("private fixture unreachable; inspect service/ACL independently of login")
	}
	who, e := lc.WhoIs(ctx, conn.RemoteAddr().String())
	conn.Close()
	if e != nil || who.Node == nil || strings.TrimSuffix(who.Node.Name, ".") != "blaine.tail0f2ece.ts.net" || string(who.Node.StableID) != "nYBs8Z3gD511CNTRL" {
		return errors.New("destination node identity lookup mismatch")
	}
	tr := &http.Transport{DialContext: s.Dial}
	defer tr.CloseIdleConnections()
	hc := &http.Client{Transport: tr, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("redirect denied") }}
	result, e := streamProbe(ctx, hc, "http://"+destination)
	if e != nil {
		return e
	}
	result["hub_visibility_wait_ms"] = readyMS
	result["platform"] = runtime.GOOS + "/" + runtime.GOARCH
	result["wsl"] = strings.Contains(strings.ToLower(kernelRelease()), "microsoft")
	result["node_id"] = node
	result["node_name"] = string(b)
	result["node_reused"] = reused
	result["first_observation"] = !reused
	result["destination_node_id"] = string(who.Node.StableID)
	result["tsnet_version"] = "v1.102.4"
	result["source_commit"] = spikeCommit
	result["scope"] = "isolated private transport fixture; not production Blaine handshake or Task acceptance"
	closeErr := s.Close()
	closed = true
	if closeErr != nil {
		return errors.New("tsnet close failed")
	}
	result["clean_close"] = true
	emit(result)
	return nil
}

var payload = func() []byte {
	b := make([]byte, 1<<20)
	for i := range b {
		b[i] = byte(i)
	}
	return b
}()

type fixture struct {
	mu     sync.Mutex
	closed map[string]bool
}

func (f *fixture) handler(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	if len(id) != 32 {
		http.Error(w, "invalid test id", 400)
		return
	}
	if r.URL.Path == "/closed" {
		f.mu.Lock()
		v := f.closed[id]
		f.mu.Unlock()
		json.NewEncoder(w).Encode(v)
		return
	}
	if r.URL.Path != "/stream" {
		http.NotFound(w, r)
		return
	}
	f.mu.Lock()
	if len(f.closed) >= 128 {
		f.mu.Unlock()
		http.Error(w, "fixture capacity reached", 503)
		return
	}
	f.closed[id] = false
	f.mu.Unlock()
	c, e := websocket.Accept(w, r, &websocket.AcceptOptions{Subprotocols: []string{"blaine-spike-v1"}})
	if e != nil {
		return
	}
	defer c.CloseNow()
	defer func() { f.mu.Lock(); f.closed[id] = true; f.mu.Unlock() }()
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	c.SetReadLimit(2 << 20)
	if e = c.Write(ctx, websocket.MessageBinary, []byte{0, 1, 128, 255}); e != nil {
		return
	}
	for {
		typ, b, e := c.Read(ctx)
		if e != nil {
			return
		}
		if e = c.Write(ctx, typ, b); e != nil {
			return
		}
	}
}
func streamProbe(ctx context.Context, hc *http.Client, base string) (map[string]any, error) {
	result, err := streamOnce(ctx, hc, base, false)
	if err != nil {
		return nil, err
	}
	if _, err = streamOnce(ctx, hc, base, true); err != nil {
		return nil, err
	}
	result["explicit_cancellation"] = true
	result["fresh_connection_after_disconnect"] = true
	return result, nil
}
func streamOnce(ctx context.Context, hc *http.Client, base string, explicit bool) (map[string]any, error) {
	id := randomID()
	ws := strings.Replace(base, "http://", "ws://", 1) + "/stream?id=" + id
	c, _, e := websocket.Dial(ctx, ws, &websocket.DialOptions{HTTPClient: hc, Subprotocols: []string{"blaine-spike-v1"}})
	if e != nil {
		return nil, errors.New("WebSocket fixture negotiation failed")
	}
	defer c.CloseNow()
	c.SetReadLimit(2 << 20)
	typ, b, e := c.Read(ctx)
	if e != nil || typ != websocket.MessageBinary || !bytes.Equal(b, []byte{0, 1, 128, 255}) {
		return nil, errors.New("unsolicited server binary message mismatch")
	}
	if e = c.Write(ctx, websocket.MessageBinary, payload); e != nil {
		return nil, e
	}
	typ, b, e = c.Read(ctx)
	if e != nil || typ != websocket.MessageBinary || !bytes.Equal(b, payload) {
		return nil, errors.New("binary roundtrip mismatch")
	}
	blocked, cancel := context.WithTimeout(ctx, 100*time.Millisecond)
	expected := error(context.DeadlineExceeded)
	if explicit {
		cancel()
		blocked, cancel = context.WithCancel(ctx)
		timer := time.AfterFunc(100*time.Millisecond, cancel)
		defer timer.Stop()
		expected = context.Canceled
	}
	defer cancel()
	_, _, e = c.Read(blocked)
	if !errors.Is(e, expected) {
		return nil, errors.New("blocked read did not respect cancellation/deadline")
	}
	c.CloseNow()
	gone := false
	for i := 0; i < 10; i++ {
		req, _ := http.NewRequestWithContext(ctx, "GET", base+"/closed?id="+id, nil)
		res, e := hc.Do(req)
		if e != nil {
			return nil, e
		}
		e = json.NewDecoder(io.LimitReader(res.Body, 128)).Decode(&gone)
		res.Body.Close()
		if e != nil {
			return nil, e
		}
		if gone {
			break
		}
		select {
		case <-time.After(100 * time.Millisecond):
		case <-ctx.Done():
			return nil, ctx.Err()
		}
	}
	if !gone {
		return nil, errors.New("server did not observe disconnect")
	}
	return map[string]any{"status": "PASS_FIXTURE", "server_initiated_binary": true, "binary_roundtrip_bytes": len(payload), "read_deadline": true, "server_observed_disconnect": true}, nil
}
func serve(parent context.Context) error {
	fs := flag.NewFlagSet("serve", flag.ContinueOnError)
	bind := fs.String("bind", "127.0.0.1:49173", "loopback or designated Blaine Tailscale IP only")
	if e := fs.Parse(os.Args[2:]); e != nil {
		return e
	}
	if *bind != "127.0.0.1:49173" && *bind != "100.94.139.5:49173" {
		return errors.New("fixture bind must be loopback or designated host private IP")
	}
	ln, e := net.Listen("tcp", *bind)
	if e != nil {
		return e
	}
	defer ln.Close()
	f := &fixture{closed: map[string]bool{}}
	handler := http.Handler(http.HandlerFunc(f.handler))
	if *bind == "100.94.139.5:49173" {
		lc := new(local.Client)
		ctx, cancel := context.WithTimeout(parent, 5*time.Second)
		st, err := lc.StatusWithoutPeers(ctx)
		cancel()
		if err != nil || st.Self == nil || string(st.Self.ID) != "nYBs8Z3gD511CNTRL" {
			return errors.New("fixture must run on the verified designated Blaine host")
		}
		owner := st.Self.UserID
		handler = http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
			defer cancel()
			who, err := lc.WhoIs(ctx, r.RemoteAddr)
			if err != nil || who.Node == nil || who.Node.User != owner || len(who.Node.Tags) != 0 {
				http.Error(w, "peer denied", 403)
				return
			}
			// Identity is derived from the actual socket, never an HTTP header or body.
			log.Printf("fixture peer_node=%s route=%s", who.Node.StableID, r.URL.Path)
			f.handler(w, r)
		})
	}
	server := &http.Server{Handler: handler, ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 10 * time.Second, ErrorLog: log.New(io.Discard, "", 0)}
	ctx, cancel := context.WithTimeout(parent, 20*time.Minute)
	defer cancel()
	go func() { <-ctx.Done(); server.Close() }()
	fmt.Fprintln(os.Stderr, "Private disposable fixture listening:", *bind, "(20 minute maximum; no Task/runtime access)")
	e = server.Serve(ln)
	if e == http.ErrServerClosed {
		return nil
	}
	return e
}
