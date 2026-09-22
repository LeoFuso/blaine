package platform

import (
	"context"
	"encoding/json"
	"fmt"
	"net/netip"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"blaine.local/client/internal/process"
)

const ProbeTimeout = 8 * time.Second
const AuthTimeout = 3 * time.Minute

// Network is a privacy projection, never raw vendor JSON. Unknown is distinct
// from false. It deliberately omits names, addresses, peers, keys and login URLs.
type Network struct {
	Owner          string `json:"owner"`
	Installed      string `json:"installed"`
	CLI            bool   `json:"cli_available"`
	Daemon         string `json:"daemon"`
	Auth           string `json:"authentication"`
	Device         string `json:"device"`
	Tailnet        bool   `json:"tailnet_visible"`
	Addresses      int    `json:"address_count"`
	HealthWarnings int    `json:"health_warning_count"`
	Version        string `json:"version"`
	WSL            bool   `json:"wsl"`
	HostReuse      string `json:"host_network_reuse"`
	Code           string `json:"code"`
	Guidance       string `json:"guidance"`
	Ready          bool   `json:"ready"`
}

type CommandRunner func(context.Context, process.Spec, *os.File, func([]byte)) ([]byte, int, error)

// Tailscale extends the platform boundary without a plugin or worker framework.
// Hooks allow deterministic fixtures that cannot invoke real host mutations.
type Tailscale struct {
	Platform Platform
	Lookup   func(string) (string, error)
	ReadFile func(string) ([]byte, error)
	Stat     func(string) (os.FileInfo, error)
	Run      CommandRunner
}

func (p Platform) Tailscale() *Tailscale {
	return &Tailscale{p, p.LookPath, os.ReadFile, os.Stat, process.Capture}
}
func (t *Tailscale) command(ctx context.Context, executable string, args ...string) ([]byte, int, error) {
	ctx, cancel := context.WithTimeout(ctx, ProbeTimeout)
	defer cancel()
	spec := process.Spec{Executable: executable, Args: args}
	if t.Platform.Kind == "darwin" && len(args) > 0 && args[0] == "status" {
		spec.Env = []string{"TAILSCALE_BE_CLI=1"}
	}
	return t.Run(ctx, spec, nil, nil)
}
func (t *Tailscale) executable(name string) string {
	p, e := t.Lookup(name)
	if e != nil || !filepath.IsAbs(p) {
		return ""
	}
	return p
}
func (t *Tailscale) exists(path string) bool { _, e := t.Stat(path); return e == nil }
func (t *Tailscale) cli() string {
	if t.Platform.Kind == "wsl" {
		return t.executable("tailscale.exe")
	}
	if t.Platform.Kind == "darwin" {
		// Prefer the app's documented CLI over a possibly competing brew daemon.
		const bundle = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
		if f, e := t.Stat(bundle); e == nil && !f.IsDir() && f.Mode()&0111 != 0 {
			return bundle
		}
	}
	return t.executable("tailscale")
}
func (t *Tailscale) Inspect(ctx context.Context) Network {
	n := Network{Owner: "linux-system", Installed: "absent", Daemon: "unknown", Auth: "unknown", Device: "unknown", HostReuse: "not-applicable", Code: "INSTALL_REQUIRED", Guidance: "Install Tailscale using https://tailscale.com/docs/install/linux ."}
	switch t.Platform.Kind {
	case "darwin":
		n.Owner = "macos-native"
		n.Guidance = "Install the native Standalone app from https://tailscale.com/download/mac ; complete macOS VPN/system-extension authorization."
		if t.exists("/Applications/Tailscale.app") {
			n.Installed = "app-present"
			n.Code = "CLI_REQUIRED"
			n.Guidance = "Open Tailscale, complete native authorization, and enable its CLI integration; then run blaine connect again."
		}
	case "wsl":
		n.Owner = "windows-host"
		n.WSL = true
		n.Installed = "unknown"
		n.HostReuse = "unverified"
		n.Code = "WINDOWS_HOST_UNAVAILABLE"
		n.Guidance = "On Windows, install/sign in to Tailscale at https://tailscale.com/download/windows . Make tailscale.exe available through WSL interop. Host absence cannot be distinguished from disabled interop here."
	}
	cli := t.cli()
	if cli == "" {
		return n
	}
	n.CLI = true
	n.Installed = "present"
	data, code, err := t.command(ctx, cli, "status", "--json")
	if err != nil || code != 0 {
		n.Code = "DAEMON_UNAVAILABLE"
		n.Guidance = "Tailscale status is unavailable. Check the tailscaled service and local socket permissions; run blaine doctor again."
		if n.WSL {
			n.Guidance = "Windows Tailscale or WSL executable interop is unavailable. Check the native Windows app/service and WSL interop."
		}
		if t.Platform.Kind == "darwin" {
			n.Code = "NATIVE_AUTHORIZATION_REQUIRED"
			n.Guidance = "Open the Tailscale app and complete VPN/system-extension authorization in macOS Settings, then retry."
		}
		return n
	}
	n = parseNetwork(data, n)
	if t.Platform.Kind == "darwin" && !t.exists("/Applications/Tailscale.app") {
		n.Owner = "macos-cli-unverified"
		n.Ready = false
		n.Code = "MACOS_OWNER_UNVERIFIED"
		n.Guidance = "A CLI is available but the native Tailscale app was not found in /Applications. Confirm its installation and ownership before onboarding; Blaine will not start a competing daemon."
	}
	if n.WSL {
		// A responding guest daemon is a topology ambiguity even if logged out.
		if local := t.executable("tailscale"); local != "" {
			_, code, err := t.command(ctx, local, "status", "--json")
			if err == nil && code == 0 {
				n.Ready = false
				n.Code = "TOPOLOGY_CONFLICT"
				n.Guidance = "A WSL Tailscale daemon also responds. Select one network owner explicitly; Blaine will not change either daemon."
				return n
			}
		}
		n.Ready = false
		if n.Code == "LOGIN_REQUIRED" || n.Code == "STOPPED" {
			n.Guidance = "Connect/sign in through the native Windows Tailscale app, then retry. WSL guest reachability still needs live verification."
		}
		if n.Code == "NETWORK_READY" {
			n.Code = "WSL_UNVERIFIED"
			n.Guidance = "Windows Tailscale is connected. WSL2 version and guest tailnet reachability need a live verification spike; host status alone does not prove reuse. No guest daemon will be installed."
		}
	}
	return n
}

var versionPattern = regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+(?:-t[0-9a-f]+-g[0-9a-f]+)?$`)

func parseNetwork(data []byte, n Network) Network {
	var s struct {
		Version      string
		BackendState string
		TUN          *bool
		Self         *struct {
			Online       bool
			TailscaleIPs []string
			Expired      bool
		}
		TailscaleIPs   []string
		CurrentTailnet *struct{}
		Health         []string
	}
	if json.Unmarshal(data, &s) != nil || s.BackendState == "" {
		n.Code = "MALFORMED_STATUS"
		n.Guidance = "Tailscale returned an unrecognized status. Update/check the native client and retry."
		return n
	}
	n.Daemon = "available"
	if versionPattern.MatchString(s.Version) {
		n.Version = s.Version
	}
	n.Tailnet = s.CurrentTailnet != nil
	n.HealthWarnings = len(s.Health)
	for _, value := range s.TailscaleIPs {
		if addr, err := netip.ParseAddr(value); err == nil && (netip.MustParsePrefix("100.64.0.0/10").Contains(addr) || netip.MustParsePrefix("fd7a:115c:a1e0::/48").Contains(addr)) {
			n.Addresses++
		}
	}
	switch s.BackendState {
	case "NeedsLogin", "NoState":
		n.Auth = "required"
		n.Code = "LOGIN_REQUIRED"
		n.Guidance = "Sign in using Tailscale's normal browser login."
	case "NeedsMachineAuth":
		n.Auth = "device-approval-required"
		n.Code = "DEVICE_APPROVAL_REQUIRED"
		n.Guidance = "Ask your tailnet administrator to approve this device in Tailscale, then retry."
	case "Stopped":
		n.Code = "STOPPED"
		n.Device = "stopped"
		n.Guidance = "Tailscale is disconnected. Connect it using the native app or CLI, then retry."
	case "Starting":
		n.Code = "STARTING"
		n.Device = "starting"
		n.Guidance = "Tailscale is starting; retry shortly."
	case "Running":
		n.Auth = "authenticated"
		n.Device = "offline"
		n.Code = "NETWORK_UNAVAILABLE"
		n.Guidance = "Check native Tailscale connectivity and health warnings; no Blaine host has been contacted."
		if s.Self != nil && s.Self.Expired {
			n.Auth = "required"
			n.Code = "LOGIN_REQUIRED"
			n.Guidance = "Tailscale device authentication expired. Sign in through Tailscale."
			break
		}
		if s.Self != nil && s.Self.Online {
			n.Device = "online"
		}
		if n.Device == "online" && n.Tailnet && n.Addresses > 0 && n.HealthWarnings == 0 && s.TUN != nil && *s.TUN {
			n.Ready = true
			n.Code = "NETWORK_READY"
			n.Guidance = "Local Tailscale network prerequisite ready; remote reachability is checked in a later E0 stage."
		}
	default:
		n.Code = "UNKNOWN_STATE"
		n.Guidance = "Tailscale returned an unsupported state. Check the native application and retry."
	}
	return n
}

// Authenticate does not elevate, change operator grants, reset preferences or
// force reauthentication. Only a strict vendor login URL may reach the terminal.
func (t *Tailscale) Authenticate(ctx context.Context, in *os.File, display func(string)) error {
	if t.Platform.Kind == "wsl" {
		return fmt.Errorf("Complete login in the native Windows Tailscale app; WSL host reuse remains unverified.")
	}
	ctx, cancel := context.WithTimeout(ctx, AuthTimeout)
	defer cancel()
	cli := t.cli()
	if cli == "" {
		return fmt.Errorf("Tailscale CLI is unavailable; enable native CLI integration and retry.")
	}
	if t.Platform.Kind == "darwin" {
		if !t.exists("/Applications/Tailscale.app") {
			return fmt.Errorf("Confirm native Tailscale app ownership before login.")
		}
		open := t.executable("open")
		if open == "" {
			return fmt.Errorf("Open Tailscale and complete native login/authorization, then retry.")
		}
		_, code, err := t.command(ctx, open, "-a", "/Applications/Tailscale.app")
		if err != nil || code != 0 {
			return fmt.Errorf("Open Tailscale manually and complete native login/authorization, then retry.")
		}
		display("Connect/sign in and complete any VPN authorization in the Tailscale app.")
		return t.waitReady(ctx)
	}
	pending := ""
	seen := map[string]bool{}
	consume := func(chunk []byte) {
		pending += string(chunk)
		for {
			i := strings.IndexByte(pending, '\n')
			if i < 0 {
				break
			}
			line := strings.TrimSpace(pending[:i])
			pending = pending[i+1:]
			if loginURL.MatchString(line) && !seen[line] {
				seen[line] = true
				display("Open this Tailscale login URL in your browser: " + line)
			}
		}
		if len(pending) > 4096 {
			pending = ""
		}
	}
	_, code, err := t.Run(ctx, process.Spec{Executable: cli, Args: []string{"up", "--timeout=3m"}}, in, consume)
	consume([]byte("\n"))
	if ctx.Err() != nil {
		return ctx.Err()
	}
	if code == 130 || code == 143 {
		return context.Canceled
	}
	if err != nil || code != 0 {
		return fmt.Errorf("Tailscale login did not complete. If local permission was denied, an administrator must complete native Tailscale onboarding (sudo tailscale up). Blaine does not retain elevated access. Retry when ready.")
	}
	return t.waitReady(ctx)
}

var loginURL = regexp.MustCompile(`^https://login\.tailscale\.com/a/[a-zA-Z0-9]+$`)

func (t *Tailscale) waitReady(ctx context.Context) error {
	for {
		n := t.Inspect(ctx)
		if n.Ready {
			return nil
		}
		if n.Code == "DEVICE_APPROVAL_REQUIRED" {
			return fmt.Errorf("%s", n.Guidance)
		}
		timer := time.NewTimer(time.Second)
		select {
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		case <-timer.C:
		}
	}
}
