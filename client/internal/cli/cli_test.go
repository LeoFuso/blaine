package cli

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"blaine.local/client/internal/process"
)

func invoke(t *testing.T, args ...string) (int, string, string) {
	t.Helper()
	root := t.TempDir()
	open := func(name string) *os.File {
		f, err := os.Create(filepath.Join(root, name))
		if err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { f.Close() })
		return f
	}
	s := process.Streams{In: open("in"), Out: open("out"), Err: open("err")}
	code := Run(context.Background(), args, s)
	out, err := os.ReadFile(s.Out.Name())
	if err != nil {
		t.Fatal(err)
	}
	diagnostic, err := os.ReadFile(s.Err.Name())
	if err != nil {
		t.Fatal(err)
	}
	return code, string(out), string(diagnostic)
}
func TestCommandsAndVersion(t *testing.T) {
	code, out, err := invoke(t, "version")
	if code != 0 || !strings.HasPrefix(out, "blaine 0.1.0-dev protocol=1 commit=unknown go=") || err != "" {
		t.Fatal(code, out, err)
	}
	code, out, err = invoke(t, "version", "--json")
	var value map[string]any
	if code != 0 || json.Unmarshal([]byte(out), &value) != nil || value["client_version"] != "0.1.0-dev" || err != "" {
		t.Fatal(code, out, err)
	}
	for _, cmd := range []string{"connect", "disconnect"} {
		code, out, err = invoke(t, cmd)
		if code != 2 || !strings.Contains(out, `"status":"NOT_IMPLEMENTED"`) || err != "" {
			t.Fatal(code, out, err)
		}
	}
}
func TestAllMalformedACPKeepsStdoutEmpty(t *testing.T) {
	for _, args := range [][]string{nil, {"unknown"}, {"version", "extra"}, {"doctor", "--json", "extra"}, {"connect", "--host", "anything"}, {"disconnect", "extra"}, {"acp", "--json"}, {"acp", "--fixture"}, {"acp", "--fixture", "bogus"}, {"acp", "--fixture", "echo", "extra"}, {"acp", "--fixture-worker", "bogus"}, {"acp", "--exec", "/bin/sh"}} {
		code, out, err := invoke(t, args...)
		if code != 64 || out != "" || err == "" {
			t.Fatal(args, code, out, err)
		}
	}
	code, out, err := invoke(t, "acp")
	if code != 2 || out != "" || !strings.Contains(err, "NOT_CONFIGURED") {
		t.Fatal(code, out, err)
	}
}
func TestDoctorJSON(t *testing.T) {
	code, out, err := invoke(t, "doctor", "--json")
	var result map[string]any
	if code != 2 || err != "" || json.Unmarshal([]byte(out), &result) != nil || result["overall"] != "NOT_READY" {
		t.Fatal(code, out, err)
	}
}
