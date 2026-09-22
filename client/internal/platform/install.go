package platform

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"blaine.local/client/internal/process"
)

type InstallPlan struct{ Kind, Summary, Guidance, Repository string }

func (t *Tailscale) Installation() InstallPlan {
	if t.Platform.Kind == "darwin" {
		return InstallPlan{Kind: "native", Summary: "Open the official Tailscale macOS download page", Guidance: "Install the Standalone app from https://tailscale.com/download/mac . Approve the signed installer and native VPN/system extension, enable CLI integration, then retry."}
	}
	if t.Platform.Kind == "wsl" {
		return InstallPlan{Kind: "manual", Guidance: "Install/sign in to native Windows Tailscale at https://tailscale.com/download/windows . WSL host reuse needs live verification; no Linux daemon will be installed."}
	}
	manual := InstallPlan{Kind: "manual", Guidance: "Use your distribution's official Tailscale package instructions at https://pkgs.tailscale.com/stable/ , then run blaine connect again."}
	data, err := t.ReadFile("/etc/os-release")
	if err != nil {
		return manual
	}
	values := map[string]string{}
	for _, line := range strings.Split(string(data), "\n") {
		k, v, ok := strings.Cut(line, "=")
		if ok {
			values[k] = strings.Trim(v, "\"'")
		}
	}
	distro, release := values["ID"], values["VERSION_CODENAME"]
	supported := map[string]string{"ubuntu": " jammy noble questing resolute ", "debian": " bullseye bookworm trixie "}
	if release == "" || !strings.Contains(supported[distro], " "+release+" ") {
		return manual
	}
	for _, name := range []string{"apt-get", "sudo", "install"} {
		if t.executable(name) == "" {
			return manual
		}
	}
	repository := "https://pkgs.tailscale.com/stable/" + distro + "/" + release
	// Reuse only the exact official signed-by repository; otherwise require review.
	if source, e := t.ReadFile("/etc/apt/sources.list.d/tailscale.list"); e == nil {
		expected := repositorySource(repository)
		var lines []string
		for _, line := range strings.Split(string(source), "\n") {
			line = strings.TrimSpace(line)
			if line != "" && !strings.HasPrefix(line, "#") {
				lines = append(lines, line)
			}
		}
		key, e := t.Stat("/usr/share/keyrings/tailscale-archive-keyring.gpg")
		if strings.Join(lines, "\n") == strings.TrimSpace(expected) && e == nil && key.Mode().IsRegular() {
			return InstallPlan{Kind: "apt-existing", Repository: repository, Summary: "Install Tailscale from the existing official signed APT repository (sudo required)", Guidance: "APT will verify package signatures; existing repository configuration will be preserved."}
		}
	}
	// Never overwrite an existing repository/key configuration, even on retry.
	for _, path := range []string{"/etc/apt/sources.list.d/tailscale.list", "/usr/share/keyrings/tailscale-archive-keyring.gpg"} {
		if _, err := t.Stat(path); !os.IsNotExist(err) {
			manual.Guidance = "Existing Tailscale repository/key configuration needs administrator review. Use the official package instructions at https://pkgs.tailscale.com/stable/ ; Blaine will not overwrite it."
			return manual
		}
	}
	return InstallPlan{Kind: "apt", Repository: repository,
		Summary:  "Add Tailscale's official signed APT repository and install the tailscale package (sudo required)",
		Guidance: "APT will verify repository/package signatures. Repository files and the system service remain owned by the OS; Blaine stays unprivileged."}
}

// Download only the official repository bootstrap key over authenticated HTTPS.
// No redirect, arbitrary URL, script execution, or third-party binary fallback.
func vendorKey(ctx context.Context, url string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, errors.New("invalid official repository URL")
	}
	if req.URL.Scheme != "https" || req.URL.Host != "pkgs.tailscale.com" || req.URL.User != nil || !strings.HasPrefix(req.URL.Path, "/stable/") || !strings.HasSuffix(req.URL.Path, ".noarmor.gpg") {
		return nil, errors.New("untrusted repository key origin")
	}
	client := &http.Client{Timeout: 20 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("redirect refused") }}
	response, err := client.Do(req)
	if err != nil {
		return nil, errors.New("official repository key download failed")
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, errors.New("official repository key unavailable")
	}
	data, err := io.ReadAll(io.LimitReader(response.Body, 65537))
	if err != nil || len(data) < 100 || len(data) > 65536 || data[0]&0x80 == 0 {
		return nil, errors.New("official repository key invalid")
	}
	return data, nil
}
func (t *Tailscale) Install(ctx context.Context, in *os.File) error {
	return t.install(ctx, in, vendorKey)
}
func (t *Tailscale) install(ctx context.Context, in *os.File, download func(context.Context, string) ([]byte, error)) error {
	plan := t.Installation()
	if plan.Kind == "manual" {
		return errors.New(plan.Guidance)
	}
	if plan.Kind == "native" {
		executable := t.executable("open")
		if executable == "" {
			return errors.New(plan.Guidance)
		}
		_, code, err := t.command(ctx, executable, "https://tailscale.com/download/mac")
		if code != 0 || err != nil {
			return errors.New(plan.Guidance)
		}
		return errors.New("The official download page is open. Complete installation and native authorization, then run blaine connect again.")
	}
	ctx, cancel := context.WithTimeout(ctx, 5*time.Minute)
	defer cancel()
	install, apt, sudo := t.executable("install"), t.executable("apt-get"), t.executable("sudo")
	var steps [][]string
	if plan.Kind == "apt" {
		key, err := download(ctx, plan.Repository+".noarmor.gpg")
		if err != nil {
			return errors.New("Could not fetch the official Tailscale repository key; no installation attempted.")
		}
		dir, err := os.MkdirTemp("", "blaine-tailscale-install-")
		if err != nil {
			return errors.New("Cannot prepare installation files.")
		}
		defer os.RemoveAll(dir)
		// Match the vendor's signed-by source. The release/distro are allowlisted.
		source := repositorySource(plan.Repository)
		for name, data := range map[string][]byte{"key": key, "source": []byte(source)} {
			if os.WriteFile(filepath.Join(dir, name), data, 0600) != nil {
				return errors.New("Cannot prepare installation files.")
			}
		}
		steps = [][]string{
			{install, "-D", "-m", "0644", filepath.Join(dir, "key"), "/usr/share/keyrings/tailscale-archive-keyring.gpg"},
			{install, "-m", "0644", filepath.Join(dir, "source"), "/etc/apt/sources.list.d/tailscale.list"},
		}
	}
	// Enforce signature verification even if a local APT default weakened it.
	strict := []string{apt, "-o", "APT::Get::AllowUnauthenticated=false", "-o", "Acquire::AllowInsecureRepositories=false", "-o", "Acquire::AllowDowngradeToInsecureRepositories=false"}
	steps = append(steps, append(append([]string{}, strict...), "update"), append(append([]string{}, strict...), "install", "-y", "tailscale"))
	if service := t.executable("systemctl"); service != "" && t.exists("/run/systemd/system") {
		steps = append(steps, []string{service, "start", "tailscaled"})
	}
	for _, args := range steps {
		// -k with a command ignores and does not update sudo's timestamp cache.
		_, code, err := t.Run(ctx, process.Spec{Executable: sudo, Foreground: true, Args: append([]string{"-k", "--"}, args...)}, in, nil)
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if err != nil || code != 0 {
			return fmt.Errorf("Tailscale installation stopped. Completed package/repository steps may remain; use your package manager to inspect/repair them, then retry. No login was attempted.")
		}
	}
	return nil
}

func repositorySource(repository string) string {
	base, release := filepath.Split(repository)
	return "deb [signed-by=/usr/share/keyrings/tailscale-archive-keyring.gpg] " + strings.TrimSuffix(base, "/") + " " + release + " main\n"
}
