// Package platform owns workstation detection, locations and executable lookup.
// WSL uses Linux processes and distro-local paths. Its version, native Windows
// prerequisites and IDE ownership need later interop evidence, not env inference.
package platform

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

type Paths struct {
	ConfigFile string
	StateDir   string
	RuntimeDir string // Empty if no native transient location was supplied.
}

type Platform struct {
	Kind  string
	Arch  string
	Paths Paths
}

func Current() (Platform, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return Platform{}, fmt.Errorf("user home unavailable")
	}
	release := ""
	if runtime.GOOS == "linux" {
		data, err := os.ReadFile("/proc/sys/kernel/osrelease")
		if err != nil {
			return Platform{}, fmt.Errorf("Linux kernel identity unavailable")
		}
		release = string(data)
	}
	return Detect(runtime.GOOS, runtime.GOARCH, home, release, os.Getenv)
}

// Detect is pure so macOS and WSL path/detection fixtures run on any build host.
// Relative XDG overrides are rejected, avoiding cwd-dependent configuration.
func Detect(goos, arch, home, release string, env func(string) string) (Platform, error) {
	p := Platform{Kind: goos, Arch: arch}
	if !filepath.IsAbs(home) {
		return p, fmt.Errorf("user home must be absolute")
	}
	switch goos {
	case "linux":
		if strings.Contains(strings.ToLower(release), "microsoft") || strings.Contains(strings.ToLower(release), "wsl") || env("WSL_INTEROP") != "" || env("WSL_DISTRO_NAME") != "" {
			p.Kind = "wsl"
		}
		config, state := env("XDG_CONFIG_HOME"), env("XDG_STATE_HOME")
		if config == "" {
			config = filepath.Join(home, ".config")
		}
		if state == "" {
			state = filepath.Join(home, ".local", "state")
		}
		transient := env("XDG_RUNTIME_DIR")
		if !filepath.IsAbs(config) || !filepath.IsAbs(state) || (transient != "" && !filepath.IsAbs(transient)) {
			return p, fmt.Errorf("XDG locations must be absolute")
		}
		p.Paths = Paths{filepath.Join(config, "blaine", "config.json"), filepath.Join(state, "blaine"), ""}
		if transient != "" {
			p.Paths.RuntimeDir = filepath.Join(transient, "blaine")
		}
	case "darwin":
		base := filepath.Join(home, "Library", "Application Support", "Blaine")
		p.Paths = Paths{filepath.Join(base, "config.json"), filepath.Join(base, "state"), ""}
	default:
		return p, fmt.Errorf("unsupported platform; use Linux, macOS or Linux inside WSL2")
	}
	return p, nil
}

// LookPath is the single external-executable discovery hook. E0.A needs none.
func (p Platform) LookPath(name string) (string, error) { return exec.LookPath(name) }

// InspectDirectory never creates files or asserts write access from mode bits.
// Missing directories are valid for this non-persisting milestone.
func InspectDirectory(path string) (exists bool, err error) {
	for candidate := path; ; candidate = filepath.Dir(candidate) {
		info, e := os.Lstat(candidate)
		if e == nil {
			if !info.IsDir() {
				return false, fmt.Errorf("directory component is not a directory or is a symlink")
			}
			// Also inspect existing ancestors; do not silently accept symlink redirects.
			if candidate == filepath.Dir(candidate) {
				break
			}
		} else if !os.IsNotExist(e) {
			return false, fmt.Errorf("directory cannot be inspected")
		}
		if candidate == filepath.Dir(candidate) {
			break
		}
	}
	_, err = os.Lstat(path)
	return err == nil, nil
}
