package jetbrains

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func target(t *testing.T) Target {
	t.Helper()
	home := t.TempDir()
	return Target{Config: filepath.Join(home, ".jetbrains", "acp.json"), Executable: filepath.Join(home, ".local", "bin", "blaine"), Command: filepath.Join(home, ".local", "bin", "blaine"), Args: []string{"acp"}}
}
func write(t *testing.T, path, s string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(s), 0600); err != nil {
		t.Fatal(err)
	}
}
func content(t *testing.T, path string) string {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return string(b)
}
func TestNewAndRepeatedInstallation(t *testing.T) {
	x := target(t)
	s, e := Apply(x, false)
	if e != nil || s.Registered || s.Matches {
		t.Fatal(s, e)
	}
	if _, e = os.Stat(filepath.Dir(x.Config)); !os.IsNotExist(e) {
		t.Fatal("check mutated filesystem")
	}
	s, e = Apply(x, true)
	if e != nil || !s.Matches || !s.Registered || !s.Changed {
		t.Fatal(s, e)
	}
	before := content(t, x.Config)
	stat, _ := os.Stat(x.Config)
	s, e = Apply(x, true)
	after, _ := os.Stat(x.Config)
	if e != nil || s.Changed || !s.Matches || content(t, x.Config) != before || stat.ModTime() != after.ModTime() {
		t.Fatal(s, e)
	}
	if _, e = os.Stat(x.Config + ".blaine-backup"); !os.IsNotExist(e) {
		t.Fatal("unnecessary backup")
	}
	s, e = Apply(x, false)
	if e != nil || !s.Matches {
		t.Fatal(s, e)
	}
}
func TestPreserveUpdateAndBackup(t *testing.T) {
	x := target(t)
	original := `{"agent_servers":{"Other":{"command":"/other","env":{"PRIVATE":"untouched"}},"Blaine E0.C candidate":{"command":"/old","args":[],"extension":42}},"default_mcp_settings":{"use_idea_mcp":true},"future":9007199254740993}`
	write(t, x.Config, original)
	s, e := Apply(x, true)
	if e != nil || s.Agent != "Blaine E0.C candidate" {
		t.Fatal(s, e)
	}
	if content(t, x.Config+".blaine-backup") != original {
		t.Fatal("backup lost exact bytes")
	}
	var doc map[string]json.RawMessage
	_ = json.Unmarshal([]byte(content(t, x.Config)), &doc)
	var agents map[string]json.RawMessage
	_ = json.Unmarshal(doc["agent_servers"], &agents)
	if len(agents) != 2 || !strings.Contains(string(agents["Other"]), "untouched") || string(doc["future"]) != "9007199254740993" {
		t.Fatal("unrelated data modified")
	}
	if !strings.Contains(string(agents[s.Agent]), `"extension": 42`) {
		t.Fatal("owned entry extension lost")
	}
	first := content(t, x.Config)
	x.Command = "/updated/path/blaine"
	x.Executable = x.Command
	s, e = Apply(x, true)
	if e != nil || !s.Changed || content(t, x.Config+".blaine-backup") != first {
		t.Fatal(s, e)
	}
	files, _ := filepath.Glob(x.Config + "*backup*")
	if len(files) != 1 {
		t.Fatal(files)
	}
	info, _ := os.Stat(x.Config + ".blaine-backup")
	if info.Mode().Perm() != 0600 {
		t.Fatal(info.Mode())
	}
}
func TestMalformedAndAmbiguousFailClosed(t *testing.T) {
	for _, raw := range []string{"", `{`, `[]`, `null`, `{} {}`, `{"agent_servers":[]}`, `{"agent_servers":null}`, `{"agent_servers":{"Other":null}}`, `{"agent_servers":{},"agent_servers":{}}`, `{"default_mcp_settings":false}`, `{"agent_servers":{"Blaine":{},"blaine":{}}}`, `{"agent_servers":{"Blaine":{},"Blaine E0.C candidate":{}}}`} {
		t.Run(raw, func(t *testing.T) {
			x := target(t)
			write(t, x.Config, raw)
			if _, err := Apply(x, true); err == nil {
				t.Fatal("accepted", raw)
			}
			if content(t, x.Config) != raw {
				t.Fatal("mutated invalid config")
			}
			if _, err := os.Stat(x.Config + ".blaine-backup"); !os.IsNotExist(err) {
				t.Fatal("backup created")
			}
		})
	}
}
func TestUnsafeFiles(t *testing.T) {
	x := target(t)
	write(t, x.Config, `{}`)
	other := filepath.Join(filepath.Dir(x.Config), "other")
	if err := os.Link(x.Config, other); err != nil {
		t.Fatal(err)
	}
	if _, err := Apply(x, true); err == nil {
		t.Fatal("hardlink accepted")
	}
	_ = os.Remove(x.Config)
	if err := os.Symlink(other, x.Config); err != nil {
		t.Fatal(err)
	}
	if _, err := Apply(x, true); err == nil {
		t.Fatal("symlink accepted")
	}
}
func TestResolveNativeAndWindowsWSL(t *testing.T) {
	home := t.TempDir()
	exe := filepath.Join(home, "bin", "blaine")
	for _, kind := range []string{"darwin", "linux"} {
		x, e := Resolve(context.Background(), home, exe, kind, "", nil)
		if e != nil || x.Config != filepath.Join(home, ".jetbrains", "acp.json") || x.Command != exe {
			t.Fatal(x, e)
		}
	}
	calls := 0
	runner := func(_ context.Context, name string, args ...string) (string, error) {
		calls++
		if calls == 1 {
			if name != "powershell.exe" {
				t.Fatal(name)
			}
			return `{"home":"C:\\Users\\User Name","launcher":"C:\\Windows\\System32\\wsl.exe"}`, nil
		}
		if name != "wslpath" || args[1] != `C:\Users\User Name` {
			t.Fatal(name, args)
		}
		return home, nil
	}
	x, e := Resolve(context.Background(), home, exe, "wsl", "Ubuntu", runner)
	if e != nil || x.Command != `C:\Windows\System32\wsl.exe` || strings.Join(x.Args, "|") != "--distribution|Ubuntu|--exec|"+exe+"|acp" {
		t.Fatal(x, e)
	}
	if _, e = Resolve(context.Background(), home, exe, "wsl", "", nil); e == nil {
		t.Fatal("missing distro accepted")
	}
}
