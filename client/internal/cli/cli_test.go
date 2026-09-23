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
	t.Setenv("PATH", root)
	t.Setenv("HOME", root)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(root, "config"))
	t.Setenv("XDG_STATE_HOME", filepath.Join(root, "state"))
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

}
func TestAllMalformedACPKeepsStdoutEmpty(t *testing.T) {
	for _, args := range [][]string{nil, {"unknown"}, {"version", "extra"}, {"doctor", "--json", "extra"}, {"connect", "--host"}, {"disconnect", "extra"}, {"acp", "--json"}, {"acp", "--fixture"}, {"acp", "--fixture", "bogus"}, {"acp", "--fixture", "echo", "extra"}, {"acp", "--fixture-worker", "bogus"}, {"acp", "--exec", "/bin/sh"}} {
		code, out, err := invoke(t, args...)
		if code != 64 || out != "" || err == "" {
			t.Fatal(args, code, out, err)
		}
	}
	code, out, err := invoke(t, "acp")
	if code != 0 || out != "" || err != "" {
		t.Fatal(code, out, err)
	}
}
func TestConnectNonInteractive(t *testing.T) {
	code, out, _ := invoke(t, "connect", "--non-interactive")
	if code != 2 || strings.Contains(out, "Network prerequisite ready") {
		t.Fatal(code, out)
	}
}
func TestDoctorHumanJSONParity(t *testing.T) {
	_, out, _ := invoke(t, "doctor", "--json")
	var r struct {
		Checks []struct{ ID, Status, Code, Summary, Remediation string }
	}
	if err := json.Unmarshal([]byte(out), &r); err != nil {
		t.Fatal(err)
	}
	_, human, _ := invoke(t, "doctor")
	for _, c := range r.Checks {
		for _, part := range []string{c.ID, c.Status, c.Code, c.Summary, c.Remediation} {
			if !strings.Contains(human, part) {
				t.Fatalf("missing %q", part)
			}
		}
	}
}
func TestDoctorJSON(t *testing.T) {
	code, out, err := invoke(t, "doctor", "--json")
	var result map[string]any
	if code != 2 || err != "" || json.Unmarshal([]byte(out), &result) != nil || result["overall"] != "NOT_READY" {
		t.Fatal(code, out, err)
	}
}
