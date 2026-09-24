package connection

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"blaine.local/client/internal/platform"
	"blaine.local/client/internal/process"
)

func paired(t *testing.T) Profile {
	t.Helper()
	p, e := New("blaine", "leofuso")
	if e != nil {
		t.Fatal(e)
	}
	p.ServerID = "server-1"
	return p
}
func response() Response {
	return Response{1, "server-1", "0.1.0-e0c", Range{1, 1}, 1, Peer{"device-1", "principal-1", "leofuso", "trusted-transport"}, "not-implemented", []string{"handshake-v1", "acp-ndjson", "no-workspace-effects"}, map[string]string{"runtime": "PASS", "restate": "PASS", "mirix": "PASS", "generation": "PASS", "embeddings": "PASS"}}
}
func TestHandshake(t *testing.T) {
	cases := []struct {
		name   string
		change func(*Response)
	}{
		{"server mismatch", func(r *Response) { r.ServerID = "another" }},
		{"missing identity", func(r *Response) { r.Peer.Device = "" }},
		{"claimed identity", func(r *Response) { r.Peer.Source = "request-json" }},
		{"wrong user", func(r *Response) { r.Peer.SSHUser = "root" }},
		{"incompatible", func(r *Response) { r.Protocol = Range{2, 3} }},
		{"downgrade", func(r *Response) { r.Selected = 0 }},
		{"missing feature", func(r *Response) { r.Features = r.Features[:2] }},
		{"missing readiness", func(r *Response) { delete(r.Readiness, "runtime") }},
		{"unknown readiness", func(r *Response) { r.Readiness["mirix"] = "UNKNOWN" }},
		{"failed readiness", func(r *Response) { r.Readiness["generation"] = "FAIL" }},
		{"revoked", func(r *Response) { r.Registration = "revoked" }},
	}
	p := paired(t)
	good, _ := json.Marshal(response())
	if _, e := Validate(good, p); e != nil {
		t.Fatal(e)
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r := response()
			c.change(&r)
			b, _ := json.Marshal(r)
			if _, e := Validate(b, p); e == nil {
				t.Fatal("accepted invalid handshake")
			}
		})
	}
	for _, b := range [][]byte{append([]byte("banner\n"), good...), append(good, good...), []byte(`{"schema_version":1,"schema_version":1}`), []byte(`null`)} {
		if _, e := Validate(b, p); e == nil {
			t.Fatal("accepted malformed control")
		}
	}
}
func TestProfile(t *testing.T) {
	p := paired(t)
	path := filepath.Join(t.TempDir(), "private", "config.json")
	if e := SaveNew(path, p); e != nil {
		t.Fatal(e)
	}
	before, _ := os.ReadFile(path)
	got, e := Load(path)
	if e != nil || got != p {
		t.Fatalf("%+v %v", got, e)
	}
	if e = SaveNew(path, p); e == nil {
		t.Fatal("overwrote concurrent profile")
	}
	after, _ := os.ReadFile(path)
	if string(before) != string(after) {
		t.Fatal("changed existing bytes")
	}
	if e = os.Chmod(path, 0644); e != nil {
		t.Fatal(e)
	}
	if _, e = Load(path); e == nil {
		t.Fatal("accepted public config")
	}
	link := filepath.Join(t.TempDir(), "link")
	if e = os.Symlink(path, link); e != nil {
		t.Fatal(e)
	}
	if _, e = Load(link); e == nil {
		t.Fatal("accepted symlink")
	}
	for _, host := range []string{"-oProxyCommand=x", "host;id", "host\n", "a@b", ""} {
		if _, e = New(host, "leofuso"); e == nil {
			t.Fatal("accepted host", host)
		}
	}
	for _, user := range []string{"root;id", "-lroot", "a@b", ""} {
		if _, e = New("blaine", user); e == nil {
			t.Fatal("accepted user", user)
		}
	}
}
func TestPrivateTransport(t *testing.T) {
	for _, ip := range []string{"100.64.0.1", "100.127.255.254", "fd7a:115c:a1e0::1"} {
		if !Private(ip) {
			t.Fatal(ip)
		}
	}
	for _, ip := range []string{"127.0.0.1", "192.168.1.1", "8.8.8.8", "::1", "::ffff:100.64.0.1", "example.com"} {
		if Private(ip) {
			t.Fatal(ip)
		}
	}
	args := strings.Join(SSHArgs(paired(t), "100.64.0.1", "handshake"), " ")
	for _, value := range []string{"-F /dev/null", "-T", "BatchMode=yes", "StrictHostKeyChecking=yes", "UpdateHostKeys=no", "PreferredAuthentications=none", "PubkeyAuthentication=no", "ControlMaster=no", "HostKeyAlias=blaine", "-l leofuso", "blaine-host-connection"} {
		if !strings.Contains(args, value) {
			t.Fatal("missing", value)
		}
	}
	_, e := (SSH{Platform: platform.Platform{Kind: "wsl"}}).command(context.Background(), paired(t), "handshake")
	if e == nil || !strings.Contains(e.Error(), "WSL_UNVERIFIED") {
		t.Fatal(e)
	}
}
func TestControlSeparationAndDeadline(t *testing.T) {
	// Real pipes/processes, synthetic executable. No SSH or live host is claimed.
	dir := t.TempDir()
	helper := filepath.Join(dir, "helper")
	if e := os.WriteFile(helper, []byte("#!/bin/sh\ncat\nprintf 'stderr diagnostic' >&2\n"), 0700); e != nil {
		t.Fatal(e)
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	out, code, e := control(ctx, process.Spec{Executable: helper}, []byte("{\"ok\":true}\n"))
	if e != nil || code != 0 || string(out) != "{\"ok\":true}\n" {
		t.Fatalf("%q %d %v", out, code, e)
	}
	if e = os.WriteFile(helper, []byte("#!/bin/sh\nsleep 10\n"), 0700); e != nil {
		t.Fatal(e)
	}
	ctx2, cancel2 := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel2()
	start := time.Now()
	_, _, e = control(ctx2, process.Spec{Executable: helper}, []byte("hello"))
	if e == nil || time.Since(start) > time.Second {
		t.Fatal("deadline did not terminate control")
	}
}

func TestFramedProcess(t *testing.T) {
	for _, tc := range []struct {
		name, script string
		wantCode     int
		want         string
	}{
		{"duplex", "read line\nprintf '%s\\n' '{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{}}'\nprintf diagnostic >&2\n", 0, "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{}}\n"},
		{"banner", "printf 'welcome\\n'\n", 1, ""},
		{"exit", "read line\nexit 23\n", 23, ""},
		{"unanswered", "read line\nexit 0\n", 1, ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			dir := t.TempDir()
			helper := filepath.Join(dir, "helper")
			if e := os.WriteFile(helper, []byte("#!/bin/sh\n"+tc.script), 0700); e != nil {
				t.Fatal(e)
			}
			in, iw, _ := os.Pipe()
			out, ow, _ := os.Pipe()
			errout, ew, _ := os.Pipe()
			defer in.Close()
			defer iw.Close()
			defer out.Close()
			defer ow.Close()
			defer errout.Close()
			defer ew.Close()
			ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			collected := make(chan string, 1)
			go func() { b, _ := io.ReadAll(out); collected <- string(b) }()
			_, _ = iw.Write([]byte("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"session/prompt\",\"params\":{}}\n"))
			iw.Close()
			code, e := Framed(ctx, process.Spec{Executable: helper}, process.Streams{In: in, Out: ow, Err: ew})
			ow.Close()
			ew.Close()
			if code != tc.wantCode {
				t.Fatalf("code %d err %v", code, e)
			}
			if got := <-collected; got != tc.want {
				t.Fatalf("stdout %q", got)
			}
		})
	}
}

func TestFramedEOFAndBlockedOutput(t *testing.T) {
	for _, blocked := range []bool{false, true} {
		t.Run(fmt.Sprint(blocked), func(t *testing.T) {
			dir := t.TempDir()
			helper := filepath.Join(dir, "helper")
			script := "#!/bin/sh\nsleep 10\n"
			if blocked {
				script = "#!/bin/sh\nwhile true; do printf '%s\\n' '{\"jsonrpc\":\"2.0\",\"method\":\"session/update\",\"params\":{}}'; done\n"
			}
			if e := os.WriteFile(helper, []byte(script), 0700); e != nil {
				t.Fatal(e)
			}
			in, iw, _ := os.Pipe()
			out, ow, _ := os.Pipe()
			null, _ := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
			defer in.Close()
			defer iw.Close()
			defer out.Close()
			defer ow.Close()
			defer null.Close()
			iw.Close()
			start := time.Now()
			ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			defer cancel()
			code, _ := Framed(ctx, process.Spec{Executable: helper}, process.Streams{In: in, Out: ow, Err: null})
			if code == 0 || time.Since(start) > 2500*time.Millisecond {
				t.Fatal("EOF or backpressure retained transport", code, time.Since(start))
			}
		})
	}
}

func TestHandshakeProcessFixtures(t *testing.T) {
	good, _ := json.Marshal(response())
	for _, tc := range []struct {
		name, body string
		ok         bool
	}{
		{"compatible", "read line\nprintf '%s\\n' '" + string(good) + "'\n", true},
		{"offline", "printf 'offline fixture' >&2\nexit 255\n", false},
		{"host key mismatch", "printf 'host key mismatch fixture' >&2\nexit 255\n", false},
		{"check-mode action", "printf 'https://login.tailscale.com/fixture-secret' >&2\nexit 255\n", false},
		{"check-mode waiting", "sleep 10\n", false},
		{"stdout banner", "read line\nprintf 'welcome\\n'\nprintf '%s\\n' '" + string(good) + "'\n", false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "helper")
			if e := os.WriteFile(path, []byte("#!/bin/sh\n"+tc.body), 0700); e != nil {
				t.Fatal(e)
			}
			ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
			defer cancel()
			_, e := handshake(ctx, paired(t), process.Spec{Executable: path})
			if (e == nil) != tc.ok {
				t.Fatal(e)
			}
			if e != nil && strings.Contains(e.Error(), "fixture-secret") {
				t.Fatal("secret diagnostic escaped")
			}
		})
	}
}
