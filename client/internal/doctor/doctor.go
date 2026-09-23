// Package doctor provides read-only observations and versioned reporting.
package doctor

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"blaine.local/client/internal/buildinfo"
	"blaine.local/client/internal/platform"
)

type Check struct {
	ID          string `json:"id"`
	Status      string `json:"status"`
	Code        string `json:"code"`
	Summary     string `json:"summary"`
	Remediation string `json:"remediation"`
	ObservedAt  string `json:"observed_at"`
}
type Report struct {
	SchemaVersion int     `json:"schema_version"`
	Timestamp     string  `json:"timestamp"`
	Overall       string  `json:"overall"`
	Checks        []Check `json:"checks"`
}

// Exit follows the Hub contract: internal > incompatible > local > remote.
// UNKNOWN required checks can never produce READY.
func Exit(checks []Check) int {
	code := 0
	for _, c := range checks {
		if c.Status == "PASS" || c.Status == "NOT_APPLICABLE" {
			continue
		}
		next := 3
		switch c.Code {
		case "INTERNAL_ERROR":
			next = 1
		case "INCOMPATIBLE":
			next = 4
		case "LOCAL_INVALID", "NOT_CONFIGURED", "NOT_IMPLEMENTED", "WSL_UNVERIFIED":
			next = 2
		}
		rank := map[int]int{0: 0, 3: 1, 2: 2, 4: 3, 1: 4}
		if rank[next] > rank[code] {
			code = next
		}
	}
	return code
}

func Inspect() Report { return InspectContext(context.Background()) }

func InspectContext(_ context.Context) Report {
	now := time.Now().UTC().Format(time.RFC3339)
	r := Report{SchemaVersion: 1, Timestamp: now, Overall: "NOT_READY"}
	add := func(id, status, code, summary, remediation string) {
		r.Checks = append(r.Checks, Check{id, status, code, summary, remediation, now})
	}
	add("client", "PASS", "OK", buildinfo.Current().String(), "")
	p, err := platform.Current()
	if err != nil {
		add("platform", "FAIL", "LOCAL_INVALID", err.Error(), "Use a supported platform and absolute user/XDG paths.")
	} else {
		add("platform", "PASS", "OK", fmt.Sprintf("%s/%s", p.Kind, p.Arch), "")
		if p.Kind == "wsl" {
			add("wsl_version", "UNKNOWN", "WSL_UNVERIFIED", "WSL markers detected; WSL2 and Windows interop are unverified", "Verify the selected distribution with wsl.exe --list --verbose on Windows; guest route proof remains required.")
		}
		add("transport", "PASS", "OK", "Embedded tsnet; system Tailscale is not required", "")

		for _, path := range []struct{ id, value string }{{"config_directory", filepath.Dir(p.Paths.ConfigFile)}, {"state_directory", p.Paths.StateDir}} {
			exists, err := platform.InspectDirectory(path.value)
			if err != nil {
				add(path.id, "FAIL", "LOCAL_INVALID", err.Error(), "Resolve inaccessible, non-directory or symlink components.")
			} else if exists {
				add(path.id, "PASS", "OK", "Directory exists; no write attempted", "")
			} else {
				add(path.id, "PASS", "OK", "Location valid; no client state needs to be written", "")
			}
		}
		_, e := os.Lstat(filepath.Join(p.Paths.StateDir, "direct-v1", "node-id"))
		if e != nil {
			add("connection", "UNKNOWN", "NOT_CONFIGURED", "Embedded connection has not been verified", "Use Blaine ACP authentication or blaine connect.")
		} else {
			add("connection", "UNKNOWN", "REMOTE_UNAVAILABLE", "Stored identity exists; current reachability was not probed", "Run blaine connect for a fresh authenticated handshake.")
		}

	}
	if executable, err := os.Executable(); err != nil || !filepath.IsAbs(executable) {
		add("execution", "FAIL", "LOCAL_INVALID", "Cannot resolve running executable", "Run an installed standalone binary.")
	} else {
		add("execution", "PASS", "OK", "Standalone executable resolved", "")
	}
	// Stable check IDs are the extension boundary. Replace each placeholder with
	// actual read-only observation in its owning slice; never infer downstream PASS.
	for _, id := range []string{"registration", "remote_blaine", "restate", "mirix", "qwen", "intellij_acp"} {
		add(id, "UNKNOWN", "NOT_IMPLEMENTED", "Not implemented in E0.C", "Registration and integrated onboarding remain E0.D–E0.F gates.")
	}
	if Exit(r.Checks) == 0 {
		r.Overall = "READY"
	}
	return r
}

// NetworkChecks is shared by both doctor renderers and never includes raw
// command output, identities, health text, IP addresses or authentication URLs.
func NetworkChecks(n platform.Network, now string) []Check {
	status := "FAIL"
	if n.Ready {
		status = "PASS"
	}
	summary := "Network prerequisite is not ready"
	if n.Ready {
		summary = "Local Tailscale network prerequisite ready"
	}
	checks := []Check{{"tailscale", status, n.Code, summary, n.Guidance, now}}
	add := func(id, value string, ok bool) {
		state, code := "UNKNOWN", "LOCAL_INVALID"
		if ok {
			state, code = "PASS", "OK"
		}
		checks = append(checks, Check{id, state, code, value, "", now})
	}
	add("tailscale_installation", n.Installed, n.Installed == "present" || n.Installed == "app-present")
	add("tailscale_owner", n.Owner, true)
	add("tailscale_cli", fmt.Sprintf("available=%t", n.CLI), n.CLI)
	add("tailscale_daemon", n.Daemon, n.Daemon == "available")
	add("tailscale_auth", n.Auth, n.Auth == "authenticated")
	add("tailscale_device", fmt.Sprintf("%s; tailnet_visible=%t; addresses=%d; health_warnings=%d; version=%s", n.Device, n.Tailnet, n.Addresses, n.HealthWarnings, n.Version), n.Device == "online" && n.Tailnet && n.Addresses > 0 && n.HealthWarnings == 0)
	add("wsl_environment", fmt.Sprintf("detected=%t", n.WSL), true)
	if n.WSL {
		add("wsl_host_reuse", n.HostReuse, false)
	}
	return checks
}
