package direct

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"blaine.local/client/internal/process"
	"blaine.local/client/internal/wire"
)

func frontendFixture(t *testing.T, input string) (string, error) {
	t.Helper()
	root := t.TempDir()
	in, err := os.Create(filepath.Join(root, "input"))
	if err != nil {
		t.Fatal(err)
	}
	defer in.Close()
	if _, err = in.WriteString(input); err != nil {
		t.Fatal(err)
	}
	if _, err = in.Seek(0, 0); err != nil {
		t.Fatal(err)
	}
	out, err := os.Create(filepath.Join(root, "output"))
	if err != nil {
		t.Fatal(err)
	}
	defer out.Close()
	diagnostic, err := os.Create(filepath.Join(root, "diagnostic"))
	if err != nil {
		t.Fatal(err)
	}
	defer diagnostic.Close()
	state := filepath.Join(root, "state")
	err = ACP(context.Background(), state, process.Streams{In: in, Out: out, Err: diagnostic})
	b, readErr := os.ReadFile(out.Name())
	if readErr != nil {
		t.Fatal(readErr)
	}
	if _, stateErr := os.Stat(state); !os.IsNotExist(stateErr) {
		t.Fatal("local envelope created network identity")
	}
	return string(b), err
}

func TestACPKotlinDiscriminatorIsNotAuthority(t *testing.T) {
	// Reconstructed from the reported unknown-field failure and Kotlin model;
	// not a captured IDE frame and not evidence of a live remote session.
	for _, kind := range []string{"com.agentclientprotocol.rpc.JsonRpcRequest", "untrusted-label"} {
		initialize := `{"type":"` + kind + `","jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientInfo":{"name":"JetBrains-fixture","version":"fixture"},"clientCapabilities":{"terminal":true}}}`
		session := `{"type":"` + kind + `","jsonrpc":"2.0","id":"s","method":"session/new","params":{"cwd":"/fixture","mcpServers":[]}}`
		output, err := frontendFixture(t, initialize+"\n"+session+"\n")
		if err != nil {
			t.Fatal(err)
		}
		lines := strings.Split(strings.TrimSpace(output), "\n")
		if len(lines) != 2 {
			t.Fatal(output)
		}
		var first, second map[string]json.RawMessage
		if json.Unmarshal([]byte(lines[0]), &first) != nil || json.Unmarshal([]byte(lines[1]), &second) != nil {
			t.Fatal(output)
		}
		if string(first["id"]) != "1" || string(second["id"]) != `"s"` || !strings.Contains(lines[0], `"agentCapabilities":{}`) || !strings.Contains(lines[1], "AUTH_REQUIRED") {
			t.Fatal(output)
		}
		if strings.Contains(output, "terminal") || strings.Contains(output, kind) {
			t.Fatal("auxiliary field granted authority or leaked", output)
		}
	}
}
func TestACPDiscriminatorDoesNotRelaxValidation(t *testing.T) {
	for _, input := range []string{
		`{"type":{},"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}`,
		`{"type":"a","type":"b","jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}`,
		`{"type":"a","jsonrpc":"1.0","id":1,"method":"initialize","params":{"protocolVersion":1}}`,
		`{"type":"a","jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":99}}`,
		`{"type":"a","unexpected":true,"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1}}`,
		`{"type":"a","jsonrpc":"2.0","id":1,"method":"session/new","params":{"mcpServers":[{"name":"untrusted"}]}}`,
	} {
		output, err := frontendFixture(t, input+"\n")
		if err == nil || output != "" {
			t.Fatal("unsafe envelope accepted", err, output)
		}
	}
	// The private handshake and application identity decoder remains closed-schema.
	var hello Hello
	if wire.Decode([]byte(`{"type":"com.agentclientprotocol.rpc.JsonRpcRequest"}`), &hello) == nil {
		t.Fatal("private handshake accepted ACP-only discriminator")
	}
}
