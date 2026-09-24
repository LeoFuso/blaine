package platform

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"blaine.local/client/internal/process"
)

const running = `{"BackendState":"Running","Version":"1.102.4-t3caf7d9e7-g084ee3b64","TUN":true,"Self":{"Online":true},"CurrentTailnet":{},"TailscaleIPs":["100.64.0.1","fd7a:115c:a1e0::1"],"Health":[]}`

func fakeTailscale(t *testing.T, kind string) *Tailscale {
	t.Helper()
	return &Tailscale{Platform: Platform{Kind: kind}, Lookup: func(string) (string, error) { return "", os.ErrNotExist }, ReadFile: func(string) ([]byte, error) { return nil, os.ErrNotExist }, Stat: func(string) (os.FileInfo, error) { return nil, os.ErrNotExist }, Run: func(context.Context, process.Spec, *os.File, func([]byte)) ([]byte, int, error) {
		t.Fatal("unexpected process")
		return nil, 1, nil
	}}
}
func TestStatusProjection(t *testing.T) {
	for _, tc := range []struct {
		name, data, code, auth string
		ready                  bool
	}{
		{"authenticated", running, "NETWORK_READY", "authenticated", true},
		{"logged out", `{"BackendState":"NeedsLogin","AuthURL":"https://login.tailscale.com/a/secret"}`, "LOGIN_REQUIRED", "required", false},
		{"no state", `{"BackendState":"NoState"}`, "LOGIN_REQUIRED", "required", false},
		{"approval", `{"BackendState":"NeedsMachineAuth"}`, "DEVICE_APPROVAL_REQUIRED", "device-approval-required", false},
		{"stopped", `{"BackendState":"Stopped"}`, "STOPPED", "unknown", false},
		{"starting", `{"BackendState":"Starting"}`, "STARTING", "unknown", false},
		{"unknown", `{"BackendState":"secret-token"}`, "UNKNOWN_STATE", "unknown", false},
		{"malformed", `secret-token`, "MALFORMED_STATUS", "unknown", false},
		{"empty", `{}`, "MALFORMED_STATUS", "unknown", false},
		{"offline", strings.Replace(running, `"Online":true`, `"Online":false`, 1), "NETWORK_UNAVAILABLE", "authenticated", false},
		{"expired", strings.Replace(running, `"Online":true`, `"Online":true,"Expired":true`, 1), "LOGIN_REQUIRED", "required", false},
		{"userspace", strings.Replace(running, `"TUN":true`, `"TUN":false`, 1), "NETWORK_UNAVAILABLE", "authenticated", false},
		{"no address", strings.Replace(running, `["100.64.0.1","fd7a:115c:a1e0::1"]`, `["invalid"]`, 1), "NETWORK_UNAVAILABLE", "authenticated", false},
		{"warnings redacted", strings.Replace(running, `"Health":[]`, `"Health":["secret-token"]`, 1), "NETWORK_UNAVAILABLE", "authenticated", false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			adapter := fakeTailscale(t, "linux")
			adapter.Lookup = func(string) (string, error) { return "/usr/bin/tailscale", nil }
			adapter.Run = func(ctx context.Context, s process.Spec, _ *os.File, _ func([]byte)) ([]byte, int, error) {
				if strings.Join(s.Args, " ") != "status --json" {
					t.Fatal(s)
				}
				if _, ok := ctx.Deadline(); !ok {
					t.Fatal("unbounded")
				}
				return []byte(tc.data), 0, nil
			}
			n := adapter.Inspect(context.Background())
			if n.Code != tc.code || n.Auth != tc.auth || n.Ready != tc.ready {
				t.Fatal(n)
			}
			if strings.Contains(fmt.Sprint(n), "secret") {
				t.Fatal("leaked status")
			}
		})
	}
}
func TestMissingAndDaemonFailure(t *testing.T) {
	a := fakeTailscale(t, "linux")
	if n := a.Inspect(context.Background()); n.Code != "INSTALL_REQUIRED" || n.Installed != "absent" {
		t.Fatal(n)
	}
	a.Lookup = func(string) (string, error) { return "/bin/tailscale", nil }
	a.Run = func(context.Context, process.Spec, *os.File, func([]byte)) ([]byte, int, error) {
		return []byte("authkey-secret"), 1, errors.New("token-secret")
	}
	if n := a.Inspect(context.Background()); n.Code != "DAEMON_UNAVAILABLE" || strings.Contains(fmt.Sprint(n), "secret") {
		t.Fatal(n)
	}
}
func TestPlatformOwnership(t *testing.T) {
	for _, kind := range []string{"darwin", "wsl"} {
		t.Run(kind, func(t *testing.T) {
			a := fakeTailscale(t, kind)
			n := a.Inspect(context.Background())
			if kind == "wsl" && (n.Code != "WINDOWS_HOST_UNAVAILABLE" || n.Installed != "unknown" || n.HostReuse != "unverified") {
				t.Fatal(n)
			}
			a.Lookup = func(name string) (string, error) {
				if name == "tailscale.exe" || kind == "darwin" {
					return "/fake/" + name, nil
				}
				return "", os.ErrNotExist
			}
			a.Run = func(context.Context, process.Spec, *os.File, func([]byte)) ([]byte, int, error) {
				return []byte(running), 0, nil
			}
			n = a.Inspect(context.Background())
			if n.Ready {
				t.Fatal("unverified owner/route accepted", n)
			}
			if kind == "wsl" {
				if n.Auth != "authenticated" || n.Code != "WSL_UNVERIFIED" {
					t.Fatal(n)
				}
				a.Lookup = func(name string) (string, error) { return "/fake/" + name, nil }
				if n = a.Inspect(context.Background()); n.Code != "TOPOLOGY_CONFLICT" {
					t.Fatal(n)
				}
			}
		})
	}
}
func TestMacAppCLIAndAuthorization(t *testing.T) {
	a := fakeTailscale(t, "darwin")
	info, err := os.Stat(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	a.Stat = func(path string) (os.FileInfo, error) {
		if path == "/Applications/Tailscale.app" {
			return info, nil
		}
		return nil, os.ErrNotExist
	}
	if n := a.Inspect(context.Background()); n.Installed != "app-present" || n.Code != "CLI_REQUIRED" {
		t.Fatal(n)
	}
	file := filepath.Join(t.TempDir(), "cli")
	if os.WriteFile(file, []byte("fixture"), 0700) != nil {
		t.Fatal("fixture")
	}
	executable, _ := os.Stat(file)
	a.Stat = func(path string) (os.FileInfo, error) {
		if strings.HasSuffix(path, "/MacOS/Tailscale") {
			return executable, nil
		}
		return info, nil
	}
	a.Run = func(_ context.Context, s process.Spec, _ *os.File, _ func([]byte)) ([]byte, int, error) {
		if s.Executable != "/Applications/Tailscale.app/Contents/MacOS/Tailscale" || strings.Join(s.Env, " ") != "TAILSCALE_BE_CLI=1" {
			t.Fatal(s)
		}
		return nil, 1, nil
	}
	if n := a.Inspect(context.Background()); n.Code != "NATIVE_AUTHORIZATION_REQUIRED" {
		t.Fatal(n)
	}
	a.Run = func(context.Context, process.Spec, *os.File, func([]byte)) ([]byte, int, error) {
		return []byte(running), 0, nil
	}
	if n := a.Inspect(context.Background()); !n.Ready {
		t.Fatal(n)
	}
}
func TestAuthenticationFilteringAndRecheck(t *testing.T) {
	a := fakeTailscale(t, "linux")
	a.Lookup = func(string) (string, error) { return "/usr/bin/tailscale", nil }
	calls := 0
	a.Run = func(ctx context.Context, s process.Spec, _ *os.File, notify func([]byte)) ([]byte, int, error) {
		calls++
		if calls == 1 {
			if strings.Join(s.Args, " ") != "up --timeout=3m" {
				t.Fatal(s)
			}
			if _, ok := ctx.Deadline(); !ok {
				t.Fatal("no deadline")
			}
			for _, part := range []string{"authkey-secret\nhttps://evil.example/a/token\nhttps://login.tailscale.com/a/", "abc123\nhttps://login.tailscale.com/a/abc123\nhttps://login.tailscale.com/a/x?token=secret\n"} {
				notify([]byte(part))
			}
			return nil, 0, nil
		}
		return []byte(running), 0, nil
	}
	var shown []string
	if err := a.Authenticate(context.Background(), nil, func(s string) { shown = append(shown, s) }); err != nil {
		t.Fatal(err)
	}
	if calls != 2 || len(shown) != 1 || !strings.HasSuffix(shown[0], "/abc123") {
		t.Fatal(calls, shown)
	}
}
func TestAuthenticationCancellationAndTimeout(t *testing.T) {
	for _, timeout := range []bool{false, true} {
		a := fakeTailscale(t, "linux")
		a.Lookup = func(string) (string, error) { return "/bin/tailscale", nil }
		a.Run = func(ctx context.Context, _ process.Spec, _ *os.File, _ func([]byte)) ([]byte, int, error) {
			<-ctx.Done()
			return nil, 130, ctx.Err()
		}
		ctx, cancel := context.WithCancel(context.Background())
		want := context.Canceled
		if timeout {
			ctx, cancel = context.WithTimeout(context.Background(), time.Millisecond)
			want = context.DeadlineExceeded
		} else {
			cancel()
		}
		err := a.Authenticate(ctx, nil, func(string) { t.Fatal("output") })
		cancel()
		if !errors.Is(err, want) {
			t.Fatal(err)
		}
	}
}
func TestAuthenticationNoPermissionElevationOrLeak(t *testing.T) {
	a := fakeTailscale(t, "linux")
	a.Lookup = func(name string) (string, error) {
		if name != "tailscale" {
			t.Fatal(name)
		}
		return "/bin/tailscale", nil
	}
	a.Run = func(context.Context, process.Spec, *os.File, func([]byte)) ([]byte, int, error) {
		return []byte("secret-password"), 1, errors.New("secret-token")
	}
	err := a.Authenticate(context.Background(), nil, func(string) { t.Fatal("output") })
	if err == nil || strings.Contains(err.Error(), "secret") {
		t.Fatal(err)
	}
}

func TestSensitiveStatusFieldsAreNeverProjected(t *testing.T) {
	data := strings.TrimSuffix(running, "}") + `,"AuthURL":"https://login.tailscale.com/a/secret","PrivateKey":"secret","NodeKey":"secret","User":{"secret":"secret"},"Peer":{"secret":{"PublicKey":"secret"}}}`
	data = strings.Replace(data, `"Version":"1.102.4-t3caf7d9e7-g084ee3b64"`, `"Version":"secret-token"`, 1)
	n := parseNetwork([]byte(data), Network{})
	if !n.Ready || strings.Contains(fmt.Sprint(n), "secret") || n.Version != "" {
		t.Fatal(n)
	}
}
func TestWindowsHostProcessUnavailable(t *testing.T) {
	a := fakeTailscale(t, "wsl")
	a.Lookup = func(name string) (string, error) {
		if name == "tailscale.exe" {
			return "/windows-path/tailscale.exe", nil
		}
		return "", os.ErrNotExist
	}
	a.Run = func(context.Context, process.Spec, *os.File, func([]byte)) ([]byte, int, error) {
		return []byte("secret-error"), 1, nil
	}
	n := a.Inspect(context.Background())
	if n.Ready || n.Code != "DAEMON_UNAVAILABLE" || n.HostReuse != "unverified" || strings.Contains(fmt.Sprint(n), "secret") {
		t.Fatal(n)
	}
}
func TestMacAuthenticationNativeAppThenObservedState(t *testing.T) {
	a := fakeTailscale(t, "darwin")
	info, _ := os.Stat(t.TempDir())
	a.Stat = func(path string) (os.FileInfo, error) {
		if path == "/Applications/Tailscale.app" {
			return info, nil
		}
		return nil, os.ErrNotExist
	}
	a.Lookup = func(name string) (string, error) { return "/usr/bin/" + name, nil }
	calls := 0
	a.Run = func(_ context.Context, s process.Spec, _ *os.File, _ func([]byte)) ([]byte, int, error) {
		calls++
		if calls == 1 {
			if s.Executable != "/usr/bin/open" || strings.Join(s.Args, " ") != "-a /Applications/Tailscale.app" || len(s.Env) != 0 {
				t.Fatal(s)
			}
			return nil, 0, nil
		}
		if strings.Join(s.Args, " ") != "status --json" || strings.Join(s.Env, " ") != "TAILSCALE_BE_CLI=1" {
			t.Fatal(s)
		}
		return []byte(running), 0, nil
	}
	if err := a.Authenticate(context.Background(), nil, func(string) {}); err != nil || calls != 2 {
		t.Fatal(calls, err)
	}
}
