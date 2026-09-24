package main

import (
	"bufio"
	"context"
	"crypto/subtle"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

// This marker is not a token and authenticates nobody. Only fixture state.
func mockLogin(ctx context.Context, open func(string) error) error {
	ln, e := net.Listen("tcp", "127.0.0.1:0")
	if e != nil {
		return e
	}
	defer ln.Close()
	nonce := randomID()
	done := make(chan struct{}, 1)
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.Host != ln.Addr().String() {
			http.Error(w, "invalid host", 400)
			return
		}
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("Content-Security-Policy", "default-src 'none'; form-action 'self'; frame-ancestors 'none'")
		switch r.URL.Path {
		case "/":
			if r.Method != "GET" {
				http.Error(w, "method", 405)
				return
			}
			if subtle.ConstantTimeCompare([]byte(r.URL.Query().Get("state")), []byte(nonce)) != 1 {
				http.Error(w, "invalid state", 403)
				return
			}
			fmt.Fprintf(w, `<!doctype html><title>Blaine authentication fixture</title><h1>Local fixture only</h1><p>No account, password, OAuth provider or real authentication is involved.</p><form method="post" action="/complete"><input type="hidden" name="state" value="%s"><button>Complete mock authentication</button></form>`, nonce)
		case "/complete":
			if r.Method != "POST" {
				http.Error(w, "method", 405)
				return
			}
			r.Body = http.MaxBytesReader(w, r.Body, 1024)
			if r.ParseForm() != nil || subtle.ConstantTimeCompare([]byte(r.PostForm.Get("state")), []byte(nonce)) != 1 {
				http.Error(w, "invalid state", 403)
				return
			}
			fmt.Fprint(w, "Mock authentication complete. Return to the IDE.")
			select {
			case done <- struct{}{}:
			default:
			}
		default:
			http.NotFound(w, r)
		}
	})
	server := &http.Server{Handler: mux, ReadHeaderTimeout: 3 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 5 * time.Second}
	defer server.Close()
	go server.Serve(ln)
	if e = open("http://" + ln.Addr().String() + "/?state=" + nonce); e != nil {
		return fmt.Errorf("browser launch unavailable")
	}
	select {
	case <-done:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}
func authAgent(parent context.Context, in io.Reader, out io.Writer, dir string, open func(string) error) error {
	if e := privateDir(dir); e != nil {
		return e
	}
	marker := filepath.Join(dir, "mock-authenticated")
	authenticated := func() bool { b, e := os.ReadFile(marker); return e == nil && string(b) == "MOCK ONLY\n" }
	scanner := bufio.NewScanner(in)
	scanner.Buffer(make([]byte, 4096), 1<<20)
	enc := json.NewEncoder(out)
	for scanner.Scan() {
		var req struct {
			ID     json.RawMessage `json:"id"`
			Method string          `json:"method"`
			Params json.RawMessage `json:"params"`
		}
		if json.Unmarshal(scanner.Bytes(), &req) != nil {
			return fmt.Errorf("invalid fixture JSON")
		}
		if len(req.ID) == 0 {
			continue
		}
		var result any = map[string]any{}
		var fault any
		switch req.Method {
		case "initialize":
			result = map[string]any{"protocolVersion": 1, "agentInfo": map[string]string{"name": "blaine-architecture-fixture", "version": "0.0.0"}, "agentCapabilities": map[string]any{"auth": map[string]any{"logout": map[string]any{}}}, "authMethods": []any{map[string]string{"id": "mock-browser", "name": "Local browser fixture", "description": "No real identity provider; no Blaine authorization"}}}
		case "authenticate":
			var p struct {
				MethodID string `json:"methodId"`
			}
			_ = json.Unmarshal(req.Params, &p)
			if p.MethodID != "mock-browser" {
				fault = map[string]any{"code": -32602, "message": "Unknown method"}
				break
			}
			ctx, cancel := context.WithTimeout(parent, 2*time.Minute)
			e := mockLogin(ctx, open)
			cancel()
			if e == nil {
				e = os.WriteFile(marker, []byte("MOCK ONLY\n"), 0600)
			}
			if e != nil {
				fault = map[string]any{"code": -32000, "message": "Mock authentication incomplete"}
			}
		case "logout":
			if e := os.Remove(marker); e != nil && !os.IsNotExist(e) {
				return e
			}
		case "session/new":
			if !authenticated() {
				fault = map[string]any{"code": -32000, "message": "Authentication required"}
				break
			}
			var p struct {
				MCP []json.RawMessage `json:"mcpServers"`
			}
			_ = json.Unmarshal(req.Params, &p)
			if len(p.MCP) > 0 {
				fault = map[string]any{"code": -32602, "message": "Fixture does not accept MCP servers"}
				break
			}
			result = map[string]string{"sessionId": "fixture-session"}
		case "session/prompt":
			if !authenticated() {
				fault = map[string]any{"code": -32000, "message": "Authentication required"}
				break
			}
			_ = enc.Encode(map[string]any{"jsonrpc": "2.0", "method": "session/update", "params": map[string]any{"sessionId": "fixture-session", "update": map[string]any{"sessionUpdate": "agent_message_chunk", "content": map[string]string{"type": "text", "text": "Mock authentication succeeded. This fixture has no workspace tools, model or durable Task."}}}})
			result = map[string]string{"stopReason": "end_turn"}
		default:
			fault = map[string]any{"code": -32601, "message": "Fixture method unavailable"}
		}
		response := map[string]any{"jsonrpc": "2.0", "id": req.ID}
		if fault != nil {
			response["error"] = fault
		} else {
			response["result"] = result
		}
		if e := enc.Encode(response); e != nil {
			return e
		}
	}
	if e := scanner.Err(); e != nil {
		return e
	}
	return nil
}
