package direct

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"testing"
	"time"

	"blaine.local/client/internal/process"
	"golang.org/x/sys/unix"
)

func TestACPChild(t *testing.T) {
	if os.Getenv("BLAINE_DIRECT_CHILD") != "1" {
		return
	}
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		var r map[string]json.RawMessage
		if json.Unmarshal(scanner.Bytes(), &r) != nil {
			os.Exit(1)
		}
		b, _ := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": r["id"], "result": map[string]any{"sessionId": "fixture-session"}})
		_, _ = os.Stdout.Write(append(b, '\n'))
	}
	os.Exit(0)
}
func TestRelayEOFAndCancellation(t *testing.T) {
	for _, cancelled := range []bool{false, true} {
		t.Run(map[bool]string{false: "EOF", true: "cancel"}[cancelled], func(t *testing.T) {
			h, url, key := testHost(t)
			exe, _ := os.Executable()
			done := make(chan error, 1)
			log, e := os.Create(filepath.Join(t.TempDir(), "stderr"))
			if e != nil {
				t.Fatal(e)
			}
			defer log.Close()
			h.ACP = func(ctx context.Context, s *Session) error {
				e := RelayHost(ctx, s, process.Spec{Executable: exe, Args: []string{"-test.run=^TestACPChild$"}, Env: []string{"BLAINE_DIRECT_CHILD=1"}}, log)
				done <- e
				return e
			}
			ctx, stop := context.WithTimeout(context.Background(), 4*time.Second)
			defer stop()
			s, _, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "acp")
			if e != nil {
				t.Fatal(e)
			}
			if e = s.Send(ctx, Data, []byte("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"session/new\",\"params\":{\"cwd\":\"/fixture\",\"mcpServers\":[]}}\n")); e != nil {
				t.Fatal(e)
			}
			kind, _, e := s.Receive(ctx)
			if e != nil || kind != Data {
				t.Fatal(kind, e)
			}
			if cancelled {
				s.Close()
			} else {
				if e = s.Send(ctx, End, nil); e != nil {
					t.Fatal(e)
				}
				kind, b, e := s.Receive(ctx)
				if e != nil || kind != Exit || len(b) != 1 || b[0] != 0 {
					t.Fatal(kind, b, e)
				}
			}
			select {
			case <-done:
			case <-ctx.Done():
				t.Fatal("host subprocess did not stop")
			}
		})
	}
}
func TestACPAuthFrontendWithoutNetwork(t *testing.T) {
	root := t.TempDir()
	in, e := os.Create(filepath.Join(root, "input"))
	if e != nil {
		t.Fatal(e)
	}
	defer in.Close()
	_, _ = io.WriteString(in, "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":1,\"clientCapabilities\":{}}}\n{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"session/new\",\"params\":{\"cwd\":\"/fixture\",\"mcpServers\":[]}}\n")
	in.Seek(0, 0)
	out, _ := os.Create(filepath.Join(root, "output"))
	defer out.Close()
	diagnostic, _ := os.Create(filepath.Join(root, "stderr"))
	defer diagnostic.Close()
	state := filepath.Join(root, "state")
	if e = ACP(context.Background(), state, process.Streams{In: in, Out: out, Err: diagnostic}); e != nil {
		t.Fatal(e)
	}
	data, _ := os.ReadFile(out.Name())
	scanner := bufio.NewScanner(bytes.NewReader(data))
	var responses []map[string]any
	for scanner.Scan() {
		var r map[string]any
		if e = json.Unmarshal(scanner.Bytes(), &r); e != nil {
			t.Fatal(e)
		}
		responses = append(responses, r)
	}
	if len(responses) != 2 || responses[1]["error"].(map[string]any)["code"] != float64(-32000) {
		t.Fatal(string(data))
	}
	if _, e = os.Stat(state); !os.IsNotExist(e) {
		t.Fatal("unauthenticated initialize wrote state")
	}
}

func TestInstalledPersonalACP(t *testing.T) {
	python := os.Getenv("BLAINE_E0C_TEST_PYTHON")
	if python == "" {
		t.Skip("installed host SDK integration is opt-in")
	}
	repo := os.Getenv("BLAINE_E0C_TEST_REPOSITORY")
	h, url, key := testHost(t)
	done := make(chan error, 1)
	log, e := os.Create(filepath.Join(t.TempDir(), "runtime-stderr"))
	if e != nil {
		t.Fatal(e)
	}
	defer log.Close()
	h.ACP = func(ctx context.Context, s *Session) error {
		e := RelayHost(ctx, s, process.Spec{Executable: python, Args: []string{"-m", "runtime.personal_acp"}, Env: []string{"PYTHONPATH=" + repo, "PYTHONDONTWRITEBYTECODE=1"}}, log)
		done <- e
		return e
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	s, _, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "acp")
	if e != nil {
		t.Fatal(e)
	}
	for _, request := range []string{
		`{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{"fs":{"readTextFile":true}}}}`,
		`{"jsonrpc":"2.0","id":2,"method":"session/new","params":{"cwd":"/e0c-no-workspace-access","mcpServers":[]}}`,
	} {
		if e = s.Send(ctx, Data, []byte(request+"\n")); e != nil {
			t.Fatal(e)
		}
		kind, b, e := s.Receive(ctx)
		if e != nil || kind != Data {
			data, _ := os.ReadFile(log.Name())
			t.Fatal(kind, e, string(data))
		}
		var response map[string]json.RawMessage
		if json.Unmarshal(b, &response) != nil || response["result"] == nil || response["error"] != nil {
			t.Fatal(string(b))
		}
	}
	_ = s.Send(ctx, End, nil)
	kind, b, e := s.Receive(ctx)
	if e != nil || kind != Exit || len(b) != 1 || b[0] != 0 {
		data, _ := os.ReadFile(log.Name())
		t.Fatal(kind, b, e, string(data))
	}
	select {
	case e = <-done:
		if e != nil {
			t.Fatal(e)
		}
	case <-ctx.Done():
		t.Fatal("runtime child leaked")
	}
	// A second real ACP child loses transport without an EOF request.
	abrupt, _, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "acp")
	if e != nil {
		t.Fatal(e)
	}
	if e = abrupt.Send(ctx, Data, []byte("{\"jsonrpc\":\"2.0\",\"id\":3,\"method\":\"initialize\",\"params\":{\"protocolVersion\":1,\"clientCapabilities\":{}}}\n")); e != nil {
		t.Fatal(e)
	}
	if kind, _, e := abrupt.Receive(ctx); e != nil || kind != Data {
		t.Fatal(kind, e)
	}
	abrupt.Close()
	select {
	case <-done:
	case <-ctx.Done():
		t.Fatal("actual runtime child leaked on disconnect")
	}

}

func TestRelayCancellationUnblocksIdleInputAndBackpressuredOutput(t *testing.T) {
	h, url, key := testHost(t)
	h.ACP = func(ctx context.Context, s *Session) error {
		if _, _, e := s.Receive(ctx); e != nil {
			return e
		}
		response, _ := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": 1, "result": string(bytes.Repeat([]byte("x"), 512<<10))})
		if e := s.Send(ctx, Data, append(response, '\n')); e != nil {
			return e
		}
		_, _, e := s.Receive(ctx)
		return e
	}
	parent, stop := context.WithTimeout(context.Background(), 3*time.Second)
	defer stop()
	s, _, e := ClientHandshake(parent, dialTest(t, url), key, h.Bootstrap, "fixture-node", "acp")
	if e != nil {
		t.Fatal(e)
	}
	inR, inW := blockingPipe(t)
	defer inR.Close()
	defer inW.Close()
	outR, outW := blockingPipe(t)
	defer outR.Close()
	defer outW.Close()
	log, _ := os.Create(filepath.Join(t.TempDir(), "stderr"))
	defer log.Close()
	ctx, cancel := context.WithCancel(parent)
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- RelayClient(ctx, s, process.Streams{In: inR, Out: outW, Err: log}) }()
	_, _ = io.WriteString(inW, "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":1}}\n")
	// One byte proves the output writer started; leave the rest backpressured.
	b := make([]byte, 1)
	if _, e = outR.Read(b); e != nil {
		t.Fatal(e)
	}
	cancel()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("client relay stuck on inherited stdio")
	}
}

// Match blocking descriptors inherited by a real executable. os.Pipe enrolls its
// files in Go's poller and hid the original Close/Read deadlock in this test.
func blockingPipe(t *testing.T) (*os.File, *os.File) {
	t.Helper()
	var fds [2]int
	if e := unix.Pipe(fds[:]); e != nil {
		t.Fatal(e)
	}
	return os.NewFile(uintptr(fds[0]), "blocking-reader"), os.NewFile(uintptr(fds[1]), "blocking-writer")
}

func TestRelayRemoteExitUnblocksOpenInheritedInput(t *testing.T) {
	for _, abrupt := range []bool{false, true} {
		t.Run(map[bool]string{false: "exit", true: "disconnect"}[abrupt], func(t *testing.T) {
			h, url, key := testHost(t)
			h.ACP = func(ctx context.Context, s *Session) error {
				if abrupt {
					s.Close()
					return nil
				}
				return s.Send(ctx, Exit, []byte{0})
			}
			ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
			defer cancel()
			s, _, e := ClientHandshake(ctx, dialTest(t, url), key, h.Bootstrap, "fixture-node", "acp")
			if e != nil {
				t.Fatal(e)
			}
			inR, inW := blockingPipe(t)
			defer inR.Close()
			defer inW.Close()
			outR, outW := blockingPipe(t)
			defer outR.Close()
			defer outW.Close()
			done := make(chan error, 1)
			go func() { done <- RelayClient(ctx, s, process.Streams{In: inR, Out: outW}) }()
			select {
			case e := <-done:
				if (e != nil) != abrupt {
					t.Fatal(e)
				}
			case <-time.After(time.Second):
				t.Fatal("remote termination left input blocked")
			}
		})
	}
}
