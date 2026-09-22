package doctor

import (
	"os"
	"path/filepath"
	"testing"
)

func TestExitPriority(t *testing.T) {
	for _, tc := range []struct {
		codes []string
		want  int
	}{
		{nil, 0}, {[]string{"REMOTE_UNAVAILABLE"}, 3}, {[]string{"NOT_CONFIGURED"}, 2},
		{[]string{"NOT_IMPLEMENTED", "REMOTE_UNAVAILABLE"}, 2}, {[]string{"LOCAL_INVALID", "INCOMPATIBLE"}, 4},
		{[]string{"INCOMPATIBLE", "INTERNAL_ERROR"}, 1}, {[]string{"INTERNAL_ERROR", "INCOMPATIBLE", "LOCAL_INVALID"}, 1},
	} {
		checks := []Check{{Status: "PASS"}, {Status: "NOT_APPLICABLE"}}
		for _, code := range tc.codes {
			checks = append(checks, Check{Status: "UNKNOWN", Code: code})
		}
		if got := Exit(checks); got != tc.want {
			t.Fatalf("%v: %d", tc.codes, got)
		}
	}
}
func TestFoundationNeverReadyOrMutating(t *testing.T) {
	root := t.TempDir()
	t.Setenv("PATH", root)
	t.Setenv("HOME", root)
	t.Setenv("XDG_CONFIG_HOME", filepath.Join(root, "config"))
	t.Setenv("XDG_STATE_HOME", filepath.Join(root, "state"))
	t.Setenv("XDG_RUNTIME_DIR", "")
	r := Inspect()
	if r.Overall != "NOT_READY" || Exit(r.Checks) != 2 {
		t.Fatal(r)
	}
	seen := map[string]bool{}
	for _, c := range r.Checks {
		seen[c.ID] = true
		if c.ObservedAt == "" {
			t.Fatal(c)
		}
	}
	for _, id := range []string{"tailscale", "remote_blaine", "restate", "mirix", "qwen", "intellij_acp"} {
		if !seen[id] {
			t.Fatal(id)
		}
	}
	entries, err := os.ReadDir(root)
	if err != nil || len(entries) != 0 {
		t.Fatalf("doctor wrote state: %v %v", entries, err)
	}
}
func TestInvalidDirectory(t *testing.T) {
	root := t.TempDir()
	t.Setenv("PATH", root)
	file := filepath.Join(root, "file")
	if err := os.WriteFile(file, []byte("secret-marker"), 0600); err != nil {
		t.Fatal(err)
	}
	t.Setenv("XDG_CONFIG_HOME", file)
	t.Setenv("XDG_STATE_HOME", root)
	t.Setenv("XDG_RUNTIME_DIR", "")
	r := Inspect()
	for _, c := range r.Checks {
		if c.ID == "config_directory" && c.Status == "FAIL" {
			return
		}
	}
	t.Fatal(r)
}
