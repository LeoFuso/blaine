// Package jetbrains owns the development custom-ACP integration, not enrollment.
package jetbrains

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"reflect"
	"strings"
	"time"

	"blaine.local/client/internal/platform"
	"blaine.local/client/internal/wire"
	"golang.org/x/sys/unix"
)

type Target struct {
	Config, Executable, Command string
	Args                        []string
}
type Status struct {
	Config     string `json:"config"`
	Executable string `json:"executable"`
	Agent      string `json:"agent"`
	Registered bool   `json:"registered"`
	Matches    bool   `json:"matches"`
	Changed    bool   `json:"changed"`
}

type Runner func(context.Context, string, ...string) (string, error)

func run(ctx context.Context, name string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	out, err := exec.CommandContext(ctx, name, args...).Output()
	if err != nil || len(out) > 65536 {
		return "", errors.New("Windows IDE profile lookup failed; verify WSL interop")
	}
	return strings.TrimSpace(strings.TrimPrefix(string(out), "\ufeff")), nil
}
func Current(ctx context.Context) (Target, error) {
	p, err := platform.Current()
	if err != nil {
		return Target{}, err
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return Target{}, err
	}
	executable, err := os.Executable()
	if err != nil {
		return Target{}, err
	}
	return Resolve(ctx, home, executable, p.Kind, os.Getenv("WSL_DISTRO_NAME"), run)
}

// Resolve preserves the actual Windows IDE -> WSL process topology. No Tailscale
// or SSH command is used. Tests supply a bounded interop fixture.
func Resolve(ctx context.Context, home, executable, kind, distro string, runner Runner) (Target, error) {
	t := Target{Config: filepath.Join(home, ".jetbrains", "acp.json"), Executable: executable, Command: executable, Args: []string{"acp"}}
	if !filepath.IsAbs(home) || !filepath.IsAbs(executable) {
		return t, errors.New("absolute home and executable required")
	}
	if kind != "wsl" {
		if kind != "linux" && kind != "darwin" {
			return t, errors.New("unsupported IDE platform")
		}
		return t, nil
	}
	if distro == "" || strings.ContainsAny(distro, "\r\n\x00") {
		return t, errors.New("WSL distribution unavailable")
	}
	raw, err := runner(ctx, "powershell.exe", "-NoProfile", "-NonInteractive", "-Command", `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; @{home=[Environment]::GetFolderPath('UserProfile'); launcher=(Join-Path $env:WINDIR 'System32\wsl.exe')} | ConvertTo-Json -Compress`)
	if err != nil {
		return t, err
	}
	var info struct{ Home, Launcher string }
	if wire.Decode([]byte(raw), &info) != nil || info.Home == "" || !strings.HasSuffix(strings.ToLower(info.Launcher), `\wsl.exe`) {
		return t, errors.New("invalid Windows profile response")
	}
	windowsHome, err := runner(ctx, "wslpath", "-u", info.Home)
	if err != nil || !filepath.IsAbs(windowsHome) {
		return t, errors.New("Windows IDE home unavailable")
	}
	if st, e := os.Stat(windowsHome); e != nil || !st.IsDir() {
		return t, errors.New("Windows IDE home is not accessible")
	}
	t.Config = filepath.Join(windowsHome, ".jetbrains", "acp.json")
	t.Command = info.Launcher
	t.Args = []string{"--distribution", distro, "--exec", executable, "acp"}
	return t, nil
}

func safe(path string, directory bool) error {
	for p := path; ; p = filepath.Dir(p) {
		s, e := os.Lstat(p)
		if e != nil && !os.IsNotExist(e) {
			return errors.New("cannot inspect integration path")
		}
		if e == nil {
			if s.Mode()&os.ModeSymlink != 0 {
				return errors.New("symlink integration path refused")
			}
			if p != path && !s.IsDir() {
				return errors.New("invalid integration directory")
			}
			if p == path {
				var st unix.Stat_t
				if unix.Lstat(p, &st) != nil || st.Uid != uint32(os.Getuid()) || (directory && !s.IsDir()) || (!directory && (!s.Mode().IsRegular() || st.Nlink != 1)) {
					return errors.New("integration path must be user-owned and unlinked")
				}
			}
		}
		if p == filepath.Dir(p) {
			break
		}
	}
	return nil
}
func read(path string) ([]byte, error) {
	if err := safe(path, false); err != nil {
		return nil, err
	}
	f, err := os.OpenFile(path, os.O_RDONLY|unix.O_NOFOLLOW, 0)
	if os.IsNotExist(err) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	defer f.Close()
	b, err := io.ReadAll(io.LimitReader(f, wire.Limit+1))
	if err != nil {
		return nil, err
	}
	if len(b) > wire.Limit {
		return nil, errors.New("ACP config exceeds 1 MiB")
	}
	return b, nil
}
func object(raw []byte) (map[string]json.RawMessage, error) {
	var obj map[string]json.RawMessage
	if wire.Decode(raw, &obj) != nil || obj == nil {
		return nil, errors.New("invalid ACP JSON object; configuration unchanged")
	}
	return obj, nil
}
func encode(v any) json.RawMessage { b, _ := json.Marshal(v); return b }
func plan(t Target, original []byte) ([]byte, Status, error) {
	s := Status{Config: t.Config, Executable: t.Executable, Agent: "Blaine"}
	doc := map[string]json.RawMessage{"default_mcp_settings": encode(map[string]bool{"use_custom_mcp": false, "use_idea_mcp": false})}
	var err error
	if original != nil {
		doc, err = object(original)
		if err != nil {
			return nil, s, err
		}
	}
	if raw, ok := doc["default_mcp_settings"]; ok {
		if _, err = object(raw); err != nil {
			return nil, s, err
		}
	}
	agents := map[string]json.RawMessage{}
	if raw, ok := doc["agent_servers"]; ok {
		agents, err = object(raw)
		if err != nil {
			return nil, s, err
		}
	}
	for name, raw := range agents {
		if _, err = object(raw); err != nil {
			return nil, s, err
		}
		if strings.EqualFold(name, "Blaine") || strings.EqualFold(name, "Blaine E0.C candidate") {
			if s.Registered {
				return nil, s, errors.New("multiple Blaine entries; review ambiguous registration")
			}
			s.Agent = name
			s.Registered = true
		}
	}
	entry := map[string]json.RawMessage{}
	if s.Registered {
		entry, _ = object(agents[s.Agent])
	}
	var command string
	var args []string
	_ = json.Unmarshal(entry["command"], &command)
	_ = json.Unmarshal(entry["args"], &args)
	s.Matches = command == t.Command && reflect.DeepEqual(args, t.Args)
	entry["command"] = encode(t.Command)
	entry["args"] = encode(t.Args)
	agents[s.Agent] = encode(entry)
	doc["agent_servers"] = encode(agents)
	b, err := json.MarshalIndent(doc, "", "  ")
	return append(b, '\n'), s, err
}
func atomic(path string, b []byte) error {
	if err := safe(path, false); err != nil {
		return err
	}
	f, err := os.CreateTemp(filepath.Dir(path), ".blaine-write-")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	defer f.Close()
	if _, err = f.Write(b); err != nil {
		return err
	}
	if err = f.Sync(); err != nil {
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	return os.Rename(f.Name(), path)
}
func Apply(t Target, install bool) (Status, error) {
	var empty Status
	dir := filepath.Dir(t.Config)
	if err := safe(dir, true); err != nil {
		return empty, err
	}
	original, err := read(t.Config)
	if err != nil {
		return empty, err
	}
	desired, s, err := plan(t, original)
	if err != nil {
		return s, err
	}
	if !install || s.Matches {
		return s, nil
	}
	if os.Geteuid() == 0 {
		return s, errors.New("run JetBrains installation as the workstation user, without sudo")
	}
	backup := t.Config + ".blaine-backup"
	if err = safe(backup, false); err != nil {
		return s, err
	}
	if err = os.MkdirAll(dir, 0700); err != nil {
		return s, err
	}
	lockPath := filepath.Join(dir, ".blaine-install.lock")
	if err = safe(lockPath, false); err != nil {
		return s, err
	}
	lock, err := os.OpenFile(lockPath, os.O_CREATE|os.O_RDWR|unix.O_NOFOLLOW, 0600)
	if err != nil {
		return s, err
	}
	defer lock.Close()
	if err = unix.Flock(int(lock.Fd()), unix.LOCK_EX|unix.LOCK_NB); err != nil {
		return s, errors.New("another installer holds the ACP configuration lock")
	}
	defer unix.Flock(int(lock.Fd()), unix.LOCK_UN)
	current, err := read(t.Config)
	if err != nil {
		return s, err
	}
	if !bytes.Equal(current, original) {
		return s, errors.New("ACP config changed concurrently; rerun with configuration editor closed")
	}
	if original != nil {
		if err = atomic(backup, original); err != nil {
			return s, err
		}
	}
	if err = atomic(t.Config, desired); err != nil {
		return s, err
	}
	s.Registered = true
	s.Matches = true
	s.Changed = true
	return s, nil
}
func (s Status) String() string {
	return fmt.Sprintf("JetBrains ACP registration: registered=%t matches=%t changed=%t\nagent: %s\nexecutable: %s\nconfig: %s", s.Registered, s.Matches, s.Changed, s.Agent, s.Executable, s.Config)
}
