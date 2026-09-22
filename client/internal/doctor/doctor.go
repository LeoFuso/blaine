// Package doctor provides read-only observations and versioned reporting.
package doctor

import (
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

func Inspect() Report {
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
			add("wsl_version", "UNKNOWN", "WSL_UNVERIFIED", "WSL markers detected; WSL2 and Windows interop are unverified", "E0.B requires native Windows/WSL2 inspection.")
		}
		for _, path := range []struct{ id, value string }{{"config_directory", filepath.Dir(p.Paths.ConfigFile)}, {"state_directory", p.Paths.StateDir}} {
			exists, err := platform.InspectDirectory(path.value)
			if err != nil {
				add(path.id, "FAIL", "LOCAL_INVALID", err.Error(), "Resolve inaccessible, non-directory or symlink components.")
			} else if exists {
				add(path.id, "PASS", "OK", "Directory exists; no write attempted", "")
			} else {
				add(path.id, "PASS", "OK", "Location valid; directory absent and not needed in E0.A", "")
			}
		}
	}
	if executable, err := os.Executable(); err != nil || !filepath.IsAbs(executable) {
		add("execution", "FAIL", "LOCAL_INVALID", "Cannot resolve running executable", "Run an installed standalone binary.")
	} else {
		add("execution", "PASS", "OK", "Standalone executable resolved; no external commands required in E0.A", "")
	}
	// Stable check IDs are the extension boundary. Replace each placeholder with
	// actual read-only observation in its owning slice; never infer downstream PASS.
	for _, id := range []string{"connection", "tailscale", "remote_blaine", "restate", "mirix", "qwen", "intellij_acp"} {
		add(id, "UNKNOWN", "NOT_IMPLEMENTED", "Not implemented in E0.A", "Requires later E0 slices; onboarding is unavailable.")
	}
	if Exit(r.Checks) == 0 {
		r.Overall = "READY"
	}
	return r
}
