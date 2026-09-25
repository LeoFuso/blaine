package direct

// Experiment-only (Letta conversation spike). Copied into a scratch copy of
// client/internal/direct and run there; never part of the client module.
//
// Runs letta-acp as the host ACP process behind Blaine's real direct transport
// (ClientHandshake, Session framing, RelayHost, relayClient and both wire
// guards). Only tsnet/WhoIs admission is replaced by the package's test host,
// exactly as the existing relay tests do. The frontend's private initialize is
// emulated as ACP() does it (capabilities stripped).

import (
	"bufio"
	"context"
	"encoding/json"
	"io"
	"os"
	"strings"
	"testing"
	"time"

	"blaine.local/client/internal/process"
)

func TestLettaSpikeRelay(t *testing.T) {
	node, bin := os.Getenv("SPIKE_NODE"), os.Getenv("SPIKE_LETTA_ACP")
	if node == "" || bin == "" {
		t.Skip("spike-only")
	}
	out, _ := os.Create(os.Getenv("SPIKE_OUT"))
	defer out.Close()
	record := func(kind string, v any) {
		b, _ := json.Marshal(map[string]any{"t": time.Now().UnixMilli(), "kind": kind, "v": v})
		out.Write(append(b, '\n'))
	}
	stderr, _ := os.Create(os.Getenv("SPIKE_HOST_STDERR"))
	defer stderr.Close()
	env := strings.Split(os.Getenv("SPIKE_ACP_ENV"), "\x1f")
	h, url, key := testHost(t)
	hostDone := make(chan error, 1)
	h.ACP = func(ctx context.Context, s *Session) error {
		e := RelayHost(ctx, s, process.Spec{Executable: node, Args: []string{bin}, Env: env}, stderr)
		hostDone <- e
		return e
	}
	ctx, cancel := context.WithTimeout(context.Background(), 6*time.Minute)
	defer cancel()
	s, _, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "acp")
	if e != nil {
		t.Fatal(e)
	}
	// ACP() frontend: private initialize with clientCapabilities stripped.
	init := `{"jsonrpc":"2.0","id":"blaine-private-initialize","method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{}}}` + "\n"
	if e = s.Send(ctx, Data, []byte(init)); e != nil {
		t.Fatal(e)
	}
	kind, b, e := s.Receive(ctx)
	if e != nil || kind != Data {
		t.Fatal("private initialize", kind, e)
	}
	record("private_initialize_response", json.RawMessage(strings.TrimSpace(string(b))))

	ideIn, ideInW := io.Pipe()
	ideOutR, ideOut := io.Pipe()
	relayDone := make(chan error, 1)
	go func() { relayDone <- relayClient(ctx, cancel, s, ideIn, ideOut) }()
	responses := make(chan map[string]json.RawMessage, 64)
	go func() {
		r := bufio.NewReaderSize(ideOutR, 1<<22)
		for {
			line, e := r.ReadBytes('\n')
			if e != nil {
				close(responses)
				return
			}
			var m map[string]json.RawMessage
			json.Unmarshal(line, &m)
			if _, ok := m["method"]; ok {
				var method string
				json.Unmarshal(m["method"], &method)
				var p struct {
					Update struct {
						Kind string `json:"sessionUpdate"`
					} `json:"update"`
				}
				json.Unmarshal(m["params"], &p)
				record("ide_received_notification", map[string]string{"method": method, "update": p.Update.Kind})
				continue
			}
			responses <- m
		}
	}()
	call := func(id int, method string, params string) map[string]json.RawMessage {
		frame := `{"jsonrpc":"2.0","id":` + strings.TrimSpace(json.Number(spikeItoa(id)).String()) + `,"method":"` + method + `","params":` + params + "}\n"
		record("ide_sent", map[string]any{"id": id, "method": method})
		if _, e := ideInW.Write([]byte(frame)); e != nil {
			record("ide_write_error", e.Error())
			return nil
		}
		select {
		case r, ok := <-responses:
			if !ok {
				record("relay_closed_before_response", map[string]any{"id": id, "method": method})
				return nil
			}
			record("ide_response", map[string]any{"id": id, "method": method, "has_error": r["error"] != nil, "error": r["error"], "result_keys": spikeKeys(r["result"])})
			return r
		case e := <-relayDone:
			errText := "<nil>"
			if e != nil {
				errText = e.Error()
			}
			record("relay_terminated", map[string]any{"id": id, "method": method, "error": errText})
			relayDone <- e
			return nil
		case <-ctx.Done():
			record("timeout", map[string]any{"id": id, "method": method})
			return nil
		}
	}
	cwd, conv := os.Getenv("SPIKE_CWD"), os.Getenv("SPIKE_LOAD_CONVERSATION")
	r := call(1, "session/new", `{"cwd":"`+cwd+`","mcpServers":[]}`)
	var created struct {
		SessionID string `json:"sessionId"`
	}
	if r != nil {
		json.Unmarshal(r["result"], &created)
	}
	call(2, "session/prompt", `{"sessionId":"`+created.SessionID+`","prompt":[{"type":"text","text":"Reply with the single word READY."}]}`)
	call(3, "session/load", `{"sessionId":"`+conv+`","cwd":"`+cwd+`","mcpServers":[]}`)
	call(4, "session/prompt", `{"sessionId":"`+conv+`","prompt":[{"type":"text","text":"`+os.Getenv("SPIKE_PROMPT")+`"}]}`)
	ideInW.Close()
	select {
	case e := <-relayDone:
		errText := "<nil>"
		if e != nil {
			errText = e.Error()
		}
		record("relay_end", errText)
	case <-time.After(20 * time.Second):
		record("relay_end", "still running after input EOF")
	}
	select {
	case e := <-hostDone:
		errText := "<nil>"
		if e != nil {
			errText = e.Error()
		}
		record("host_end", errText)
	case <-time.After(10 * time.Second):
		record("host_end", "host still running")
	}
}

func spikeItoa(i int) string { b, _ := json.Marshal(i); return string(b) }

func spikeKeys(raw json.RawMessage) []string {
	var m map[string]json.RawMessage
	if json.Unmarshal(raw, &m) != nil {
		return nil
	}
	out := []string{}
	for k := range m {
		out = append(out, k)
	}
	return out
}

// The real IDE-facing frontend, before any network: what does an IDE learn from
// initialize, and can it open a session with session/load (resume)?
func TestLettaSpikeFrontendResume(t *testing.T) {
	if os.Getenv("SPIKE_OUT") == "" {
		t.Skip("spike-only")
	}
	root := t.TempDir()
	in, _ := os.Create(root + "/input")
	io.WriteString(in, `{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{"fs":{"readTextFile":true}}}}`+"\n"+
		`{"jsonrpc":"2.0","id":2,"method":"session/load","params":{"sessionId":"local-conv-15","cwd":"/fixture","mcpServers":[]}}`+"\n")
	in.Seek(0, 0)
	out, _ := os.Create(root + "/output")
	diag, _ := os.Create(root + "/stderr")
	e := ACP(context.Background(), root+"/state", process.Streams{In: in, Out: out, Err: diag})
	data, _ := os.ReadFile(out.Name())
	f, _ := os.OpenFile(os.Getenv("SPIKE_OUT"), os.O_APPEND|os.O_WRONLY, 0o600)
	defer f.Close()
	b, _ := json.Marshal(map[string]any{"kind": "frontend_transcript", "acp_return": func() string {
		if e == nil {
			return "<nil>"
		}
		return e.Error()
	}(), "ide_output": strings.Split(strings.TrimSpace(string(data)), "\n")})
	f.Write(append(b, '\n'))
}
