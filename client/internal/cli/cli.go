// Package cli owns output routing. The acp branch never receives the human/JSON
// stdout renderer: only the process relay can write its protocol stdout.
package cli

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"

	"blaine.local/client/internal/buildinfo"
	"blaine.local/client/internal/direct"
	"blaine.local/client/internal/doctor"
	"blaine.local/client/internal/fixture"
	"blaine.local/client/internal/jetbrains"
	"blaine.local/client/internal/platform"
	"blaine.local/client/internal/process"
)

func Run(ctx context.Context, args []string, streams process.Streams) int {
	diagnostic := func(s string) { fmt.Fprintln(streams.Err, "blaine: "+s) }
	usage := func() int {
		diagnostic("usage: blaine version [--json] | doctor [--json] | connect [--non-interactive] [--verify-transport] | disconnect --logout [--reset-identity] | integration jetbrains install|check [--json] | acp [--fixture echo|exit-23|wait]")
		return 64
	}
	if len(args) == 0 {
		return usage()
	}
	if args[0] == "integration" {
		if (len(args) != 3 && len(args) != 4) || args[1] != "jetbrains" || (args[2] != "install" && args[2] != "check") || (len(args) == 4 && args[3] != "--json") {
			return usage()
		}
		target, err := jetbrains.Current(ctx)
		if err != nil {
			diagnostic(err.Error())
			return 2
		}
		status, err := jetbrains.Apply(target, args[2] == "install")
		if err != nil {
			diagnostic(err.Error())
			return 2
		}
		if len(args) == 4 {
			err = json.NewEncoder(streams.Out).Encode(status)
		} else {
			_, err = fmt.Fprintln(streams.Out, status.String())
			if err == nil && args[2] == "install" {
				_, err = fmt.Fprintln(streams.Out, "Open AI Chat and select "+status.Agent+". Reload the IDE if needed. For E0.C, disable custom/IntelliJ MCP exposure for Blaine in Agents settings.")
			}
		}
		if err != nil {
			diagnostic("output write failed")
			return 1
		}
		return 0
	}
	if args[0] == "acp" {
		return acp(ctx, args[1:], streams, diagnostic, usage)
	}
	if args[0] == "connect" || args[0] == "disconnect" {
		p, err := platform.Current()
		if err != nil {
			diagnostic(err.Error())
			return 2
		}
		if args[0] == "connect" {
			nonInteractive, verifyTransport := false, false
			for _, arg := range args[1:] {
				switch {
				case arg == "--non-interactive" && !nonInteractive:
					nonInteractive = true
				case arg == "--verify-transport" && !verifyTransport:
					verifyTransport = true
				default:
					return usage()
				}
			}
			err = direct.Connect(ctx, p.Paths.StateDir, !nonInteractive, verifyTransport, streams.Out, streams.Err)
		} else {
			reset := len(args) == 3 && args[1] == "--logout" && args[2] == "--reset-identity"
			if !reset && (len(args) != 2 || args[1] != "--logout") {
				return usage()
			}
			err = direct.Logout(ctx, p.Paths.StateDir, reset)
			if err == nil {
				fmt.Fprintln(streams.Out, "Embedded Blaine network logout confirmed. Durable Tasks and system Tailscale are unchanged.")
			}
		}
		if err != nil {
			diagnostic(err.Error())
		}
		if ctx.Err() != nil {
			return 130
		}
		return direct.ExitCode(err)
	}

	jsonMode := len(args) == 2 && args[1] == "--json"
	if len(args) != 1 && !jsonMode {
		return usage()
	}
	writeJSON := func(value any) int {
		if err := json.NewEncoder(streams.Out).Encode(value); err != nil {
			diagnostic("output write failed")
			return 1
		}
		return 0
	}
	switch args[0] {
	case "version":
		info := buildinfo.Current()
		if jsonMode {
			return writeJSON(info)
		}
		if _, err := fmt.Fprintln(streams.Out, info.String()); err != nil {
			diagnostic("output write failed")
			return 1
		}
		return 0
	case "doctor":
		report := doctor.InspectContext(ctx)
		if jsonMode {
			if writeJSON(report) != 0 {
				return 1
			}
		} else {
			for _, check := range report.Checks {
				if _, err := fmt.Fprintf(streams.Out, "%-20s %-7s %s: %s\n", check.ID, check.Status, check.Code, check.Summary); err != nil {
					diagnostic("output write failed")
					return 1
				}
				if check.Remediation != "" {
					if _, err := fmt.Fprintln(streams.Out, "  "+check.Remediation); err != nil {
						return 1
					}
				}
			}
			if _, err := fmt.Fprintln(streams.Out, report.Overall+" — integrated onboarding/doctor acceptance remains E0.E–E0.F."); err != nil {
				return 1
			}
		}
		return doctor.Exit(report.Checks)

	default:
		return usage()
	}
}

func acp(ctx context.Context, args []string, s process.Streams, diagnostic func(string), usage func() int) int {
	if len(args) == 0 {
		p, err := platform.Current()
		if err != nil {
			diagnostic(err.Error())
			return 2
		}
		err = direct.ACP(ctx, p.Paths.StateDir, s)
		if err != nil {
			diagnostic(err.Error())
		}
		if ctx.Err() != nil {
			return 130
		}
		return direct.ExitCode(err)
	}
	if len(args) != 2 || !fixture.Valid(args[1]) {
		return usage()
	}
	// Private self-exec entrypoint has the same time and byte bounds as its parent.
	if args[0] == "--fixture-worker" {
		timer := timeLimit()
		defer timer()
		return fixture.Run(args[1], s.In, s.Out, s.Err)
	}
	if args[0] != "--fixture" {
		return usage()
	}
	executable, err := os.Executable()
	if err != nil {
		diagnostic("executable unavailable")
		return 1
	}
	bounded, cancel := context.WithTimeout(ctx, fixture.Timeout)
	defer cancel()
	diagnostic("E0.A byte fixture only; no ACP server or network connection")
	code, err := process.Run(bounded, process.Spec{Executable: executable, Args: []string{"acp", "--fixture-worker", args[1]}}, s)
	if errors.Is(err, context.DeadlineExceeded) {
		diagnostic("fixture deadline exceeded; child group stopped")
		return 124
	}
	if err != nil && ctx.Err() != nil {
		diagnostic("cancelled; child group stopped")
		return 130
	}
	if err != nil {
		diagnostic(err.Error())
		return 1
	}
	diagnostic(fmt.Sprintf("fixture exited: %d", code))
	return code
}
