// Package cli owns output routing. The acp branch never receives the human/JSON
// stdout renderer: only the process relay can write its protocol stdout.
package cli

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/user"
	"strings"

	"blaine.local/client/internal/buildinfo"
	"blaine.local/client/internal/connect"
	"blaine.local/client/internal/connection"
	"blaine.local/client/internal/doctor"
	"blaine.local/client/internal/fixture"
	"blaine.local/client/internal/platform"
	"blaine.local/client/internal/process"
)

func Run(ctx context.Context, args []string, streams process.Streams) int {
	diagnostic := func(s string) { fmt.Fprintln(streams.Err, "blaine: "+s) }
	usage := func() int {
		diagnostic("usage: blaine version [--json] | doctor [--json] | connect [--non-interactive] [--host NAME] | disconnect | acp [--fixture echo|exit-23|wait]")
		return 64
	}
	if len(args) == 0 {
		return usage()
	}
	if args[0] == "acp" {
		return acp(ctx, args[1:], streams, diagnostic, usage)
	}
	if args[0] == "connect" {
		host, nonInteractive := "", false
		for i := 1; i < len(args); i++ {
			switch args[i] {
			case "--non-interactive":
				if nonInteractive {
					return usage()
				}
				nonInteractive = true
			case "--host":
				if host != "" || i+1 >= len(args) {
					return usage()
				}
				i++
				host = args[i]
			default:
				return usage()
			}
		}
		p, err := platform.Current()
		if err != nil {
			diagnostic(err.Error())
			return 2
		}
		if os.Geteuid() == 0 {
			diagnostic("Run Blaine as your normal user. Only prerequisite installation may request sudo.")
			return 2
		}
		if !process.IsTerminal(streams.In) {
			nonInteractive = true
		}
		reader := bufio.NewReader(streams.In)
		confirm := func(prompt string) bool {
			if _, err := fmt.Fprint(streams.Out, prompt); err != nil {
				return false
			}
			answer := make(chan bool, 1)
			go func() {
				line, err := reader.ReadSlice('\n')
				if err != nil || len(line) > 64 {
					answer <- false
					return
				}
				value := strings.ToLower(strings.TrimSpace(string(line)))
				answer <- value == "" || value == "y" || value == "yes"
			}()
			select {
			case <-ctx.Done():
				return false
			case yes := <-answer:
				return yes
			}
		}
		if code := connect.Run(ctx, p.Tailscale(), connect.UI{In: streams.In, Out: streams.Out, Confirm: confirm, NonInteractive: nonInteractive}); code != 0 {
			return code
		}
		profile, err := connection.Load(p.Paths.ConfigFile)
		fresh := os.IsNotExist(err)
		if host != "" {
			canonical, e := p.Tailscale().HostName(ctx, host)
			if e != nil {
				diagnostic(e.Error())
				return connection.Exit(e)
			}
			host = canonical
		}
		if fresh {
			if host == "" {
				diagnostic("NOT_CONFIGURED: use blaine connect --host NAME with the operator's MagicDNS host; no tailnet scan")
				return 2
			}
			u, e := user.Current()
			if e != nil {
				diagnostic("LOCAL_INVALID: cannot determine SSH user")
				return 2
			}
			profile, err = connection.New(host, u.Username)
		} else if err == nil && host != "" && host != profile.Host {
			diagnostic("IDENTITY_MISMATCH: existing host profile preserved; explicit trusted re-pairing required")
			return 2
		}
		if err != nil {
			diagnostic("LOCAL_INVALID: connection profile unavailable or invalid")
			return 2
		}
		response, err := (connection.SSH{Platform: p}).Handshake(ctx, profile)
		if err != nil {
			diagnostic(err.Error())
			return connection.Exit(err)
		}
		if fresh {
			profile.ServerID = response.ServerID
			if err = connection.SaveNew(p.Paths.ConfigFile, profile); err != nil {
				diagnostic(err.Error())
				return 2
			}
		}
		fmt.Fprintln(streams.Out, "Host handshake verified. NOT_READY: registration (E0.D) and IntelliJ integration (E0.E) remain.")
		return 2
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
			if _, err := fmt.Fprintln(streams.Out, report.Overall+" — E0.C host gate; registration and IDE onboarding remain pending."); err != nil {
				return 1
			}
		}
		return doctor.Exit(report.Checks)
	case "disconnect":
		if jsonMode {
			return usage()
		}
		result := struct {
			SchemaVersion int    `json:"schema_version"`
			Command       string `json:"command"`
			Status        string `json:"status"`
			Milestone     string `json:"milestone"`
		}{1, args[0], "NOT_IMPLEMENTED", "E0.A"}
		if writeJSON(result) != 0 {
			return 1
		}
		return 2
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
		profile, err := connection.Load(p.Paths.ConfigFile)
		if err != nil {
			diagnostic("NOT_CONFIGURED: valid host profile required; run blaine connect --host NAME")
			return 2
		}
		code, err := (connection.SSH{Platform: p}).ACP(ctx, profile, s)
		if err != nil {
			diagnostic(err.Error())
		}
		return code
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
