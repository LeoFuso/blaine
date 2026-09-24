package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestStreamPrimitive(t *testing.T) {
	f := &fixture{closed: map[string]bool{}}
	s := httptest.NewServer(http.HandlerFunc(f.handler))
	defer s.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	r, e := streamProbe(ctx, s.Client(), s.URL)
	if e != nil {
		t.Fatal(e)
	}
	t.Log(r)
	// Fresh connections do not replay old operations; server remains available.
	if _, e = streamProbe(ctx, s.Client(), s.URL); e != nil {
		t.Fatal(e)
	}
}
func TestAgentAuthFixture(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "auth")
	opener := func(raw string) error {
		u, e := url.Parse(raw)
		if e != nil {
			return e
		}
		r, e := http.Get(raw)
		if e != nil {
			return e
		}
		io.Copy(io.Discard, r.Body)
		r.Body.Close()
		if r.StatusCode != 200 {
			t.Fatalf("page %d", r.StatusCode)
		}
		r, e = http.PostForm("http://"+u.Host+"/complete", url.Values{"state": {"wrong"}})
		if e != nil {
			return e
		}
		r.Body.Close()
		if r.StatusCode != 403 {
			t.Fatal("bad state accepted")
		}
		r, e = http.PostForm("http://"+u.Host+"/complete", url.Values{"state": {u.Query().Get("state")}})
		if e != nil {
			return e
		}
		r.Body.Close()
		if r.StatusCode != 200 {
			t.Fatal("valid state rejected")
		}
		return nil
	}
	var out bytes.Buffer
	input := `{"id":1,"method":"initialize"}
{"id":2,"method":"session/new","params":{"mcpServers":[]}}
{"id":3,"method":"authenticate","params":{"methodId":"mock-browser"}}
{"id":4,"method":"session/new","params":{"mcpServers":[]}}
`
	if e := authAgent(context.Background(), strings.NewReader(input), &out, dir, opener); e != nil {
		t.Fatal(e)
	}
	lines := strings.Split(strings.TrimSpace(out.String()), "\n")
	if len(lines) != 4 {
		t.Fatal("protocol contaminated")
	}
	var r map[string]any
	json.Unmarshal([]byte(lines[1]), &r)
	if r["error"] == nil {
		t.Fatal("missing auth gate")
	}
	json.Unmarshal([]byte(lines[3]), &r)
	if !strings.Contains(lines[3], `"sessionId"`) {
		t.Fatal(lines[3])
	}
	info, e := os.Stat(filepath.Join(dir, "mock-authenticated"))
	if e != nil || info.Mode().Perm() != 0600 {
		t.Fatal("marker permissions", e)
	}
	out.Reset()
	if e = authAgent(context.Background(), strings.NewReader(`{"id":5,"method":"session/new"}`+"\n"), &out, dir, opener); e != nil || !strings.Contains(out.String(), `"sessionId"`) {
		t.Fatal("restart persistence failed", e)
	}
	out.Reset()
	if e = authAgent(context.Background(), strings.NewReader("{\"id\":6,\"method\":\"logout\"}\n{\"id\":7,\"method\":\"session/new\"}\n"), &out, dir, opener); e != nil || !strings.Contains(out.String(), `"code":-32000`) {
		t.Fatal("logout gate failed", e)
	}
}
func TestAuthDeadline(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	if mockLogin(ctx, func(string) error { return nil }) == nil {
		t.Fatal("uncompleted login accepted")
	}
}
